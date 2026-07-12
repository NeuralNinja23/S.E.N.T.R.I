import { pcm16ToFloat32 } from "./audio";

// Exposed VAD Timing & Sensitivity Configurations
export const VAD_REDEMPTION_MS = 350; // Silence window (ms) before triggering speech finish
export const VAD_PRE_SPEECH_MS = 250;  // Minimum speech duration (ms) to trigger VAD start
export const VAD_SPEECH_PAD_MS = 480;  // Padding history limit (ms) to avoid cut-off prefixes

class PlaybackScheduler {
  private audioContext: AudioContext;
  private activeSources: Set<AudioBufferSourceNode> = new Set();
  private activeGains: Set<GainNode> = new Set();
  private nextPlayTime = 0;

  constructor(audioContext: AudioContext) {
    this.audioContext = audioContext;
  }

  enqueue(arrayBuffer: ArrayBuffer, onStart: () => void, onEnded: () => void) {
    onStart();

    const float32Array = pcm16ToFloat32(arrayBuffer);
    const audioBuffer = this.audioContext.createBuffer(1, float32Array.length, 24000);
    audioBuffer.getChannelData(0).set(float32Array);

    const source = this.audioContext.createBufferSource();
    source.buffer = audioBuffer;

    // Create GainNode for smooth crossfades and artifact-free interruptions
    const gainNode = this.audioContext.createGain();
    source.connect(gainNode);
    gainNode.connect(this.audioContext.destination);

    this.activeSources.add(source);
    this.activeGains.add(gainNode);

    const now = this.audioContext.currentTime;
    
    // Eliminate the 50ms delay: schedule back-to-back chunks with 0ms gap
    if (this.nextPlayTime < now) {
      this.nextPlayTime = now;
    }
    
    source.start(this.nextPlayTime);
    this.nextPlayTime += audioBuffer.duration;

    source.onended = () => {
      this.activeSources.delete(source);
      this.activeGains.delete(gainNode);
      source.disconnect();
      gainNode.disconnect();
      if (this.activeSources.size === 0) {
        onEnded();
      }
    };
  }

  interrupt() {
    const now = this.audioContext.currentTime;
    
    // Apply a fast exponential ramp-down to prevent clicks (50ms fade-out)
    this.activeGains.forEach((gainNode) => {
      try {
        gainNode.gain.setValueAtTime(gainNode.gain.value, now);
        gainNode.gain.exponentialRampToValueAtTime(0.0001, now + 0.05);
      } catch (e) {
        // fallback to direct mute if context state is unstable
        gainNode.gain.value = 0;
      }
    });

    // Terminate sources after fade-out completion
    setTimeout(() => {
      this.activeSources.forEach((source) => {
        try {
          source.stop();
          source.disconnect();
        } catch (e) {}
      });
      this.activeSources.clear();
      this.activeGains.clear();
    }, 55);

    this.nextPlayTime = 0;
  }

  isPlaying(): boolean {
    return this.activeSources.size > 0;
  }
}

class AudioService {
  private recordingContext: AudioContext | null = null;
  private playbackContext: AudioContext | null = null;
  private mediaStream: MediaStream | null = null;
  private scheduler: PlaybackScheduler | null = null;
  private workletNode: any = null;
  private isWorkletModuleAdded = false;

  playAudioChunk(arrayBuffer: ArrayBuffer, onStart: () => void, onEnded: () => void) {
    if (!this.playbackContext) {
      this.playbackContext = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 24000 });
      this.scheduler = new PlaybackScheduler(this.playbackContext);
    }
    this.scheduler!.enqueue(arrayBuffer, onStart, onEnded);
  }

  stopAllAudio() {
    if (this.scheduler) {
      this.scheduler.interrupt();
    }
  }

  isPlaying() {
    return this.scheduler ? this.scheduler.isPlaying() : false;
  }

  private vadInstance: any = null;
  private isUserSpeaking = false;
  private preSpeechBuffer: ArrayBuffer[] = [];
  
  // Calculate buffer history size limit dynamically based on exposed VAD configs
  private getPreSpeechLimit(): number {
    const frameSizeMs = 32; // Standard MicVAD frame duration
    return Math.round(VAD_SPEECH_PAD_MS / frameSizeMs);
  }

  async startRecording(
    onAudioChunk: (data: ArrayBuffer) => void,
    onSampleRateReady: (rate: number) => void,
    onEndOfSpeech: () => void,
    onSpeechStart: () => void
  ) {
    try {
      if (!this.playbackContext) {
        this.playbackContext = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 24000 });
        this.scheduler = new PlaybackScheduler(this.playbackContext);
      } else if (this.playbackContext.state === 'suspended') {
        await this.playbackContext.resume();
      }

      this.isUserSpeaking = false;
      this.preSpeechBuffer = [];

      if (!this.vadInstance) {
        const { MicVAD } = await import("@ricky0123/vad-web");
        
        this.vadInstance = await MicVAD.new({
          model: "v5",
          baseAssetPath: "/",          // Serve silero_vad_v5.onnx and vad.worklet.bundle.min.js locally from public/
          onnxWASMBasePath: "/",      // Serve ort-wasm-simd.wasm locally from public/
          startOnLoad: false,
          positiveSpeechThreshold: 0.45,
          negativeSpeechThreshold: 0.32,
          redemptionMs: VAD_REDEMPTION_MS,
          minSpeechMs: VAD_PRE_SPEECH_MS,
          ortConfig: (ort) => {
            ort.env.wasm.numThreads = 1;
          },
          onSpeechStart: () => {
            console.log("[Sentinel VAD] Speech started.");
            this.isUserSpeaking = true;
            onSpeechStart();

            for (const chunk of this.preSpeechBuffer) {
              onAudioChunk(chunk);
            }
            this.preSpeechBuffer = [];
          },
          onFrameProcessed: (probabilities, frame) => {
            const buffer = new ArrayBuffer(frame.length * 2);
            const view = new DataView(buffer);
            for (let i = 0; i < frame.length; i++) {
              const clamped = Math.max(-1.0, Math.min(1.0, frame[i]));
              const intVal = clamped < 0 ? clamped * 0x8000 : clamped * 0x7FFF;
              view.setInt16(i * 2, intVal, true);
            }

            if (this.isUserSpeaking) {
              onAudioChunk(buffer);
            } else {
              this.preSpeechBuffer.push(buffer);
              const limit = this.getPreSpeechLimit();
              if (this.preSpeechBuffer.length > limit) {
                this.preSpeechBuffer.shift();
              }
            }
          },
          onSpeechEnd: () => {
            console.log("[Sentinel VAD] User finished speaking.");
            this.isUserSpeaking = false;
            this.preSpeechBuffer = [];
            onEndOfSpeech();
          }
        });
      }

      onSampleRateReady(16000);
      await this.vadInstance.start();

    } catch (err) {
      console.error('[Sentinel Audio] Error starting VAD recording:', err);
      alert(`Recording Error: ${err}\nPlease verify microphone permissions.`);
      throw err;
    }
  }

  stopRecording() {
    if (this.vadInstance) {
      this.vadInstance.pause();
    }
    this.isUserSpeaking = false;
    this.preSpeechBuffer = [];
    this.stopAllAudio();
  }

  cleanupHardware() {
    if (this.vadInstance) {
      this.vadInstance.destroy();
      this.vadInstance = null;
    }
    this.isUserSpeaking = false;
    this.preSpeechBuffer = [];
    this.stopAllAudio();
  }
}

export const audioService = new AudioService();
