import { pcm16ToFloat32 } from "./audio";

class AudioService {
  private recordingContext: AudioContext | null = null;
  private playbackContext: AudioContext | null = null;
  private mediaStream: MediaStream | null = null;
  private activeSources = new Set<AudioBufferSourceNode>();
  private nextPlayTime = 0;
  private workletNode: any = null;
  private isWorkletModuleAdded = false;

  playAudioChunk(arrayBuffer: ArrayBuffer, onStart: () => void, onEnded: () => void) {
    onStart();

    if (!this.playbackContext) {
      this.playbackContext = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 24000 });
    }
    const audioContext = this.playbackContext;

    const float32Array = pcm16ToFloat32(arrayBuffer);

    const audioBuffer = audioContext.createBuffer(1, float32Array.length, 24000);
    audioBuffer.getChannelData(0).set(float32Array);

    const source = audioContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(audioContext.destination);

    this.activeSources.add(source);

    if (this.nextPlayTime < audioContext.currentTime) {
      this.nextPlayTime = audioContext.currentTime + 0.05;
    }
    source.start(this.nextPlayTime);
    this.nextPlayTime += audioBuffer.duration;

    source.onended = () => {
      this.activeSources.delete(source);
      if (this.activeSources.size === 0) {
        onEnded();
      }
    };
  }

  stopAllAudio() {
    this.activeSources.forEach((source) => {
      try {
        source.stop();
        source.disconnect();
      } catch (e) {
        // Already stopped
      }
    });
    this.activeSources.clear();
    this.nextPlayTime = 0;
  }

  isPlaying() {
    return this.activeSources.size > 0;
  }


  private vadInstance: any = null;
  private isUserSpeaking = false;
  private preSpeechBuffer: ArrayBuffer[] = [];
  private readonly PRE_SPEECH_BUFFER_LIMIT = 15; // ~480ms of history to prevent prefix cutoffs

  async startRecording(
    onAudioChunk: (data: ArrayBuffer) => void,
    onSampleRateReady: (rate: number) => void,
    onEndOfSpeech: () => void,
    onSpeechStart: () => void
  ) {
    try {
      if (!this.playbackContext) {
        this.playbackContext = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 24000 });
      } else if (this.playbackContext.state === 'suspended') {
        await this.playbackContext.resume();
      }

      this.isUserSpeaking = false;
      this.preSpeechBuffer = [];

      // Lazily import @ricky0123/vad-web to avoid SSR (Node.js) build errors
      if (!this.vadInstance) {
        const { MicVAD } = await import("@ricky0123/vad-web");
        
        this.vadInstance = await MicVAD.new({
          model: "v5",
          baseAssetPath: "/",          // Serve silero_vad_v5.onnx and vad.worklet.bundle.min.js locally from public/
          onnxWASMBasePath: "/",      // Serve ort-wasm-simd.wasm locally from public/
          startOnLoad: false,
          positiveSpeechThreshold: 0.45, // Tuned for high speech sensitivity
          negativeSpeechThreshold: 0.32,
          redemptionMs: 700,           // 700ms silence window before triggering end of speech
          minSpeechMs: 250,            // Require at least 250ms of speech to trigger VAD
          ortConfig: (ort) => {
            ort.env.wasm.numThreads = 1; // Disable multi-threading to prevent CORS/COOP/COEP issues
          },
          onSpeechStart: () => {
            console.log("[Sentinel VAD] Speech started.");
            this.isUserSpeaking = true;
            onSpeechStart();

            // Flush pre-speech padding history to avoid prefix cutoff
            for (const chunk of this.preSpeechBuffer) {
              onAudioChunk(chunk);
            }
            this.preSpeechBuffer = [];
          },
          onFrameProcessed: (probabilities, frame) => {
            // Convert Float32 resampled audio (16kHz) to PCM16
            const buffer = new ArrayBuffer(frame.length * 2);
            const view = new DataView(buffer);
            for (let i = 0; i < frame.length; i++) {
              const clamped = Math.max(-1.0, Math.min(1.0, frame[i]));
              const intVal = clamped < 0 ? clamped * 0x8000 : clamped * 0x7FFF;
              view.setInt16(i * 2, intVal, true);
            }

            if (this.isUserSpeaking) {
              // Stream active speech to backend
              onAudioChunk(buffer);
            } else {
              // Collect pre-speech padding frames
              this.preSpeechBuffer.push(buffer);
              if (this.preSpeechBuffer.length > this.PRE_SPEECH_BUFFER_LIMIT) {
                this.preSpeechBuffer.shift();
              }
            }
          },
          onSpeechEnd: () => {
            console.log("[Sentinel VAD] User finished speaking (speech end detected).");
            this.isUserSpeaking = false;
            this.preSpeechBuffer = [];
            onEndOfSpeech();
          }
        });
      }

      // Always report 16000 Hz — MicVAD resamples internally to this rate
      onSampleRateReady(16000);

      // Start VAD processing and microphone capture
      await this.vadInstance.start();

    } catch (err) {
      console.error('[Sentinel Audio] Error starting VAD recording:', err);
      alert(`Recording Error: ${err}\nPlease verify microphone permissions.`);
      throw err;
    }
  }

  stopRecording() {
    if (this.vadInstance) {
      this.vadInstance.pause(); // Stops mic stream and VAD loop
    }
    this.isUserSpeaking = false;
    this.preSpeechBuffer = [];
    this.stopAllAudio();
  }

  cleanupHardware() {
    if (this.vadInstance) {
      this.vadInstance.destroy(); // Releases ONNX session and tracks
      this.vadInstance = null;
    }
    this.isUserSpeaking = false;
    this.preSpeechBuffer = [];
    this.stopAllAudio();
  }
}

export const audioService = new AudioService();
