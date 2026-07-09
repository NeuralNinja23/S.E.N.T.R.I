/**
 * PCMProcessor — AudioWorklet
 *
 * Downsamples from hardware native rate (e.g. 48kHz) to exactly 16000 Hz
 * using linear interpolation with a persistent fractional position cursor,
 * then emits raw PCM16 little-endian buffers to the main thread.
 *
 * VAD is handled externally by vad-worker.js (Silero VAD).
 * This processor is intentionally VAD-free: it just captures and resamples.
 */
class PCMProcessor extends AudioWorkletProcessor {
  constructor() {
    super();

    this.TARGET_RATE = 16000;
    this.resampleRatio = sampleRate / this.TARGET_RATE;

    this.inputBuffer = [];
    this.fractionalPos = 0.0;

    this.OUTPUT_SAMPLES = 2048;
    this.outputBuffer = new ArrayBuffer(this.OUTPUT_SAMPLES * 2);
    this.outputView = new DataView(this.outputBuffer);
    this.outputByteOffset = 0;

    // Raw float32 buffer sent directly to VAD (bypasses int16 round-trip)
    this.VAD_FRAME = 512;
    this.vadFloat32 = new Float32Array(this.VAD_FRAME);
    this.vadOffset = 0;
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;

    const float32 = input[0];

    for (let i = 0; i < float32.length; i++) {
      this.inputBuffer.push(float32[i]);
    }

    while (this.fractionalPos + 1 < this.inputBuffer.length) {
      const idx = Math.floor(this.fractionalPos);
      const frac = this.fractionalPos - idx;

      const s0 = this.inputBuffer[idx];
      const s1 = this.inputBuffer[idx + 1] !== undefined ? this.inputBuffer[idx + 1] : s0;
      const sample = s0 + frac * (s1 - s0);

      const clamped = Math.max(-1.0, Math.min(1.0, sample));
      const intVal = clamped < 0 ? clamped * 0x8000 : clamped * 0x7FFF;

      this.outputView.setInt16(this.outputByteOffset, intVal, true);
      this.outputByteOffset += 2;

      // Also collect raw float32 for VAD (bypasses int16 round-trip)
      this.vadFloat32[this.vadOffset++] = clamped;
      if (this.vadOffset >= this.VAD_FRAME) {
        this.port.postMessage({ type: 'vad_float32', buffer: this.vadFloat32.buffer.slice(0) });
        this.vadOffset = 0;
      }

      this.fractionalPos += this.resampleRatio;

      if (this.outputByteOffset >= this.outputBuffer.byteLength) {
        this.port.postMessage(this.outputBuffer.slice(0));
        this.outputByteOffset = 0;
      }
    }

    const consumed = Math.floor(this.fractionalPos);
    if (consumed > 0 && consumed < this.inputBuffer.length) {
      this.inputBuffer.splice(0, consumed);
      this.fractionalPos -= consumed;
    }

    return true;
  }
}

registerProcessor('pcm-processor', PCMProcessor);
