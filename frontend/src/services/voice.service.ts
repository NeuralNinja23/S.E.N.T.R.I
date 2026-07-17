import { voiceStore } from "../store/voice.store";
import { websocketService } from "./websocket.service";
import { audioService } from "./audio.service";
import { speechService } from "./speech.service";

class VoiceService {
  private isRecordingRef = { current: false };

  init() {
    if (typeof window === "undefined") return;

    // Add startup log on client initialization
    voiceStore.addLog("SENTRI Online");

    // Connect WebSocket
    websocketService.connect(
      () => {
        voiceStore.setState({ isConnected: true, speakingState: "INACTIVE" });
      },
      (event) => {
        // ws message handler
        if (event.data instanceof ArrayBuffer) {
          audioService.playAudioChunk(
            event.data,
            () => voiceStore.setState({ speakingState: "SPEAKING" }),
            () => {
              // Playback callback: set LISTENING if the mic is active, otherwise INACTIVE
              if (audioService.isPlaying()) {
                voiceStore.setState({ speakingState: "SPEAKING" });
              } else {
                voiceStore.setState({ speakingState: this.isRecordingRef.current ? "LISTENING" : "INACTIVE" });
              }
            }
          );
          return;
        }

        const msg = JSON.parse(event.data);
        if (msg.type === "pong") return;

        if (msg.type === "system") {
          voiceStore.addLog(`SYS: ${msg.message}`);
        } else if (msg.type === "text") {
          voiceStore.addLog(`SENTRI: ${msg.data}`);
          if (!audioService.isPlaying()) {
            voiceStore.setState({ speakingState: "THINKING" });
          }
        } else if (msg.type === "user") {
          voiceStore.addLog(`USER: ${msg.data}`);
        } else if (msg.type === "interrupt") {
          voiceStore.addLog("SYS: Playback interrupted.");
          audioService.stopAllAudio();
          voiceStore.setState({ speakingState: "SPEAKING" });
        } else if (msg.type === "state") {
          if (msg.state === "STANDBY") {
            voiceStore.setState({ speakingState: "STANDBY" });
            voiceStore.addLog("SYS: SENTRI entered standby mode.");
            audioService.stopAllAudio();
          } else if (msg.state === "WAKING") {
            voiceStore.setState({ speakingState: "WAKING" });
            voiceStore.addLog("SYS: SENTRI is waking up...");
          } else if (msg.state === "READY") {
            voiceStore.setState({ speakingState: "INACTIVE" });
            voiceStore.addLog("SYS: SENTRI is active and ready.");
          } else if (msg.state === "THINKING") {
            if (!audioService.isPlaying()) {
              voiceStore.setState({ speakingState: "THINKING" });
            }
          }
        }
      },
      () => {
        // ws close handler
        voiceStore.setState({ isConnected: false, speakingState: "INACTIVE" });
        if (this.isRecordingRef.current) {
          this.stopRecording();
        }
      },
      (err) => {
        console.warn("WebSocket error:", err);
      }
    );

    // Start Web Speech API Recognition
    speechService.start(
      () => {
        // On Wake Word
        websocketService.send(JSON.stringify({ type: "wake_word" }));
        setTimeout(() => {
          this.startRecording();
        }, 1200);
      },
      (govCmd) => {
        // On Governance Command
        if (govCmd === "stop_speaking") {
          audioService.stopAllAudio();
        }
        websocketService.send(JSON.stringify({ type: "governance", command: govCmd }));
      },
      (userSpeech) => {
        // Speech ended callback from speechService (not used when VAD is active)
      },
      this.isRecordingRef,
      () => {
        voiceStore.setState({ speakingState: "INACTIVE" });
      }
    );

    // Add window listener for refresh cleanup
    window.addEventListener("beforeunload", this.cleanup);
  }

  sendCommand(text: string) {
    if (websocketService.isOpen()) {
      websocketService.send(JSON.stringify({ type: "command", text }));
      voiceStore.setState({ speakingState: "THINKING" });
    }
  }

  async startRecording() {
    // Guard: don't double-start
    if (this.isRecordingRef.current) return;

    const { speakingState } = voiceStore.getState();
    if (speakingState === "STANDBY" || speakingState === "WAKING") {
      return;
    }
    try {
      this.isRecordingRef.current = true;
      voiceStore.setState({ isRecording: true, speakingState: "LISTENING" });

      await audioService.startRecording(
        (pcmData) => {
          // Send raw mic PCM stream over WebSocket
          websocketService.send(pcmData);
        },
        (sampleRate) => {
          // Send rate config to backend
          websocketService.send(JSON.stringify({
            type: "config",
            sampleRate
          }));
        },
        () => {
          // VAD detected end of speech (silence completed) — submit turn
          if (websocketService.isOpen()) {
            websocketService.send(JSON.stringify({ type: "turn_complete" }));
            voiceStore.setState({ speakingState: "THINKING" });
          }
        },
        () => {
          // VAD detected start of speech — trigger interruption if Sentri is speaking
          if (audioService.isPlaying()) {
            console.log("[VoiceService] Interruption detected! Stopping playback.");
            audioService.stopAllAudio();
            websocketService.send(JSON.stringify({ type: "governance", command: "stop" }));
          }
          voiceStore.setState({ speakingState: "LISTENING" });
        }
      );
    } catch (e) {
      this.isRecordingRef.current = false;
      voiceStore.setState({ isRecording: false, speakingState: "INACTIVE" });
    }
  }

  stopSpeaking() {
    audioService.stopAllAudio();
    if (websocketService.isOpen()) {
      websocketService.send(JSON.stringify({ type: "governance", command: "stop" }));
    }
    voiceStore.setState({ speakingState: "INACTIVE" });
  }


  stopRecording() {
    this.isRecordingRef.current = false;
    voiceStore.setState({ isRecording: false, speakingState: "INACTIVE" });
    audioService.stopRecording();

    // Send definitive end-of-turn
    websocketService.send(JSON.stringify({ type: "turn_complete" }));

    // Keep speech recognition running for governance commands ("stop", etc.)
    // Auto-restart of recording happens via the onPlaybackComplete callback above.
    speechService.start(
      () => {
        websocketService.send(JSON.stringify({ type: "wake_word" }));
        setTimeout(() => {
          this.startRecording();
        }, 1200);
      },
      (govCmd) => {
        if (govCmd === "stop_speaking") {
          audioService.stopAllAudio();
        }
        websocketService.send(JSON.stringify({ type: "governance", command: govCmd }));
      },
      (userSpeech) => {
        // Automatically stop recording and submit when user finishes speaking
        if (this.isRecordingRef.current) {
          this.stopRecording();
        }
      },
      this.isRecordingRef,
      () => {
        voiceStore.setState({ speakingState: "INACTIVE" });
      }
    );
  }

  toggleRecording() {
    const { isRecording, speakingState } = voiceStore.getState();
    if (speakingState === "STANDBY") {
      this.sendCommand("EXIT_STANDBY");
      return;
    }
    if (speakingState === "WAKING") {
      return;
    }
    if (isRecording) {
      this.stopRecording();
    } else {
      if (speakingState === "SPEAKING" || speakingState === "THINKING") {
        this.stopSpeaking();
      }
      this.startRecording();
    }
  }

  cleanup = () => {
    audioService.cleanupHardware();
    speechService.stop();
    websocketService.disconnect();
    window.removeEventListener("beforeunload", this.cleanup);
  };
}

export const voiceService = new VoiceService();
