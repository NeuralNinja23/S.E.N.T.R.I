/**
 * Adaptive Energy VAD Worker
 *
 * Uses raw float32 audio frames (512 samples @ 16kHz = 32ms/frame) from the
 * AudioWorklet and computes RMS energy. Compares against a running adaptive
 * noise floor to detect speech vs silence.
 *
 * Why not Silero VAD ONNX?
 *   The ONNX model consistently outputs ~0.001 despite loud speech
 *   (amplitude 0.85+), indicating a model/runtime version incompatibility.
 *   Adaptive energy VAD is simpler, has zero external dependencies, and works
 *   perfectly given the observed amplitude ratio: speech ~0.85, silence ~0.002
 *   (a 400× difference — extremely easy to threshold).
 *
 * Messages received:
 *   { type: 'init' }                  — start VAD
 *   { type: 'audio', buffer: AB }     — 512 float32 samples
 *   { type: 'reset' }                 — clear state between turns
 *
 * Messages posted:
 *   { type: 'ready' }                 — VAD ready
 *   { type: 'speech_prob', prob }     — current frame speech probability [0,1]
 *   { type: 'end_of_speech' }         — silence after speech threshold exceeded
 */

'use strict';

// --- Tunable parameters ---
const FRAME_SAMPLES = 512;         // Must match pcm-processor.js VAD_FRAME

// Speech detection
const SPEECH_RATIO   = 4;          // RMS must be > noiseFloor * SPEECH_RATIO
const SPEECH_FLOOR   = 0.003;      // Absolute minimum RMS to ever count as speech
const MIN_SPEECH_FRAMES    = 8;    // 8 × 32ms = ~256ms of speech to arm VAD

// Silence detection
const SILENCE_RATIO  = 2.5;        // RMS must be < noiseFloor * SILENCE_RATIO
const SILENCE_FLOOR  = 0.008;      // Absolute maximum RMS to ever count as silence
const SILENCE_FRAMES_TO_END = 22;  // 22 × 32ms = ~704ms of silence to fire end_of_speech

// Noise floor adaptation
const NOISE_INIT     = 0.003;      // Starting noise floor estimate
const NOISE_ALPHA_UP   = 0.01;     // How fast noise floor rises — slower to avoid adapting to speech
const NOISE_ALPHA_DOWN = 0.005;    // How slow noise floor falls

// --- State ---
let noiseFloor = NOISE_INIT;
let speechFrameCount  = 0;
let silenceFrameCount = 0;
let vadArmed = false;
let audioBuffer = new Float32Array(0);

function computeRMS(frame) {
  let sum = 0;
  for (let i = 0; i < frame.length; i++) sum += frame[i] * frame[i];
  return Math.sqrt(sum / frame.length);
}

function resetVADState() {
  noiseFloor       = NOISE_INIT;
  speechFrameCount  = 0;
  silenceFrameCount = 0;
  vadArmed          = false;
  audioBuffer       = new Float32Array(0);
}

function processFrame(frame) {
  const rms = computeRMS(frame);

  // Detect speech / silence relative to adaptive noise floor
  const speechThreshold  = Math.max(noiseFloor * SPEECH_RATIO,  SPEECH_FLOOR);
  const silenceThreshold = Math.min(noiseFloor * SILENCE_RATIO, SILENCE_FLOOR);
  const isSpeech  = rms >= speechThreshold;
  const isSilence = rms <= silenceThreshold;

  // Adapt noise floor only in clear silence (not during ambiguous frames)
  if (isSilence) {
    noiseFloor = noiseFloor * (1 - NOISE_ALPHA_UP)   + rms * NOISE_ALPHA_UP;
  } else if (!isSpeech) {
    // Borderline frame — very slow adaptation
    noiseFloor = noiseFloor * (1 - NOISE_ALPHA_DOWN) + rms * NOISE_ALPHA_DOWN;
  }

  // Compute a normalised probability for logging
  const prob = isSpeech
    ? Math.min((rms - speechThreshold) / speechThreshold + 0.5, 1.0)
    : Math.max(rms / speechThreshold, 0);

  self.postMessage({ type: 'speech_prob', prob });

  if (isSpeech) {
    speechFrameCount++;
    silenceFrameCount = 0;
    if (speechFrameCount >= MIN_SPEECH_FRAMES) {
      vadArmed = true;
    }
  } else if (isSilence) {
    // True silence — if VAD armed, count towards end_of_speech
    if (vadArmed) {
      silenceFrameCount++;
      if (silenceFrameCount >= SILENCE_FRAMES_TO_END) {
        self.postMessage({ type: 'end_of_speech' });
        console.log(`[EnergyVAD] end_of_speech fired. noiseFloor=${noiseFloor.toFixed(5)}`);
        resetVADState();
      }
    } else {
      // Silence before arming — slowly drain speech counter so background
      // noise can't accidentally arm the VAD
      speechFrameCount = Math.max(0, speechFrameCount - 1);
    }
  } else {
    // Borderline frame (between isSilence and isSpeech) — hold all counters.
    // Do NOT reset speechFrameCount here: inter-syllable gaps should not
    // un-arm the VAD or drain the speech counter.
    silenceFrameCount = 0; // restart silence timer on any non-silent frame
  }
}

function processAudio(float32Data) {
  const merged = new Float32Array(audioBuffer.length + float32Data.length);
  merged.set(audioBuffer);
  merged.set(float32Data, audioBuffer.length);
  audioBuffer = merged;

  while (audioBuffer.length >= FRAME_SAMPLES) {
    const frame = audioBuffer.slice(0, FRAME_SAMPLES);
    audioBuffer = audioBuffer.slice(FRAME_SAMPLES);
    processFrame(frame);
  }
}

self.onmessage = (e) => {
  const { type, buffer } = e.data;

  if (type === 'init') {
    resetVADState();
    self.postMessage({ type: 'ready' });
    console.log('[EnergyVAD] Adaptive energy VAD ready.');
  } else if (type === 'audio') {
    processAudio(new Float32Array(buffer));
  } else if (type === 'reset') {
    resetVADState();
  }
};
