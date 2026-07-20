"""
generate_test_wavs.py
=====================
Synthesizes real spoken .wav files using Kokoro ONNX TTS — the same model
SENTRI uses for output — so they can be fed back in as realistic ASR input.

Run once before voice_stress_test.py:
    cd backend
    python tests/generate_test_wavs.py

Output: tests/wav/  (16 kHz, mono, PCM16 WAV files)
"""

import sys
import wave
import numpy as np
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parent.parent
RESOURCES_DIR = BACKEND_DIR / "app" / "conversation" / "resources"
WAV_OUT_DIR = Path(__file__).resolve().parent / "wav"
WAV_OUT_DIR.mkdir(exist_ok=True)

MODEL_PATH = RESOURCES_DIR / "kokoro-v1.0.onnx"
VOICES_PATH = RESOURCES_DIR / "voices-v1.0.bin"

# Target sample rate for SENTRI's ASR (Faster-Whisper base)
ASR_SAMPLE_RATE = 16_000

# All utterances we need for the stress test
UTTERANCES = {
    "greeting_hello": "Hello Sentri, good morning.",
    "greeting_punctuated": "Good morning!",
    "query_time": "What time is it right now?",
    "query_name": "What is my name?",
    "query_projects": "What projects am I currently building?",
    "query_vram": "How much VRAM is available on my GPU?",
    "query_ram": "How much RAM am I using right now?",
    "barge_in_stop": "Stop.",
    "barge_in_wait": "Wait, actually stop.",
    "compound_morning": "Good morning, check my active projects.",
    "cancel_restart_1": "Question one: what time is it?",
    "cancel_restart_2": "Question two: who am I?",
    "cancel_restart_3": "Question three: what is my name?",
}


def load_kokoro():
    """Load Kokoro ONNX model directly (same code path as model_runtime.py)."""
    import onnxruntime as ort
    from kokoro_onnx import Kokoro

    if not MODEL_PATH.exists() or not VOICES_PATH.exists():
        print(f"[ERROR] Kokoro model files not found in {RESOURCES_DIR}")
        print("  Start the backend once to auto-download them.")
        sys.exit(1)

    available = ort.get_available_providers()
    if "CUDAExecutionProvider" in available:
        print("[INFO] Loading Kokoro with CUDA...")
        try:
            sess = ort.InferenceSession(
                str(MODEL_PATH),
                providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
            )
            return Kokoro.from_session(sess, str(VOICES_PATH))
        except Exception as e:
            print(f"[WARN] CUDA failed ({e}), falling back to CPU")

    print("[INFO] Loading Kokoro with CPU...")
    sess = ort.InferenceSession(str(MODEL_PATH), providers=["CPUExecutionProvider"])
    return Kokoro.from_session(sess, str(VOICES_PATH))


def write_wav(path: Path, pcm_float: np.ndarray, sample_rate: int):
    """Convert float32 [-1,1] → PCM16 and write a proper WAV file."""
    # Resample to 16 kHz if needed (Kokoro outputs at 24 kHz)
    if sample_rate != ASR_SAMPLE_RATE:
        # Simple linear interpolation resample
        original_len = len(pcm_float)
        new_len = int(original_len * ASR_SAMPLE_RATE / sample_rate)
        indices = np.linspace(0, original_len - 1, new_len)
        pcm_float = np.interp(indices, np.arange(original_len), pcm_float)

    pcm16 = np.clip(pcm_float * 32767.0, -32768, 32767).astype(np.int16)

    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)  # mono
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(ASR_SAMPLE_RATE)
        wf.writeframes(pcm16.tobytes())

    duration = len(pcm16) / ASR_SAMPLE_RATE
    return duration


def generate_all():
    print("=" * 58)
    print(" Kokoro WAV Generator for SENTRI Voice Stress Test")
    print("=" * 58)

    kokoro = load_kokoro()

    # Use same voice as SENTRI default
    VOICE = "af_sarah"
    LANG = "en-gb"

    print(f"\nVoice: {VOICE}  |  Lang: {LANG}")
    print(f"Output: {WAV_OUT_DIR}\n")

    generated = []
    for key, text in UTTERANCES.items():
        out_path = WAV_OUT_DIR / f"{key}.wav"
        print(f"  Synthesizing '{text}' ...", end=" ", flush=True)
        try:
            samples, sr = kokoro.create(text, voice=VOICE, speed=1.0, lang=LANG)
            duration = write_wav(out_path, samples, sr)
            print(f"OK  ({duration:.2f}s, {sr} Hz -> {ASR_SAMPLE_RATE} Hz)")
            generated.append((key, out_path, duration))
        except Exception as e:
            print(f"FAIL: {e}")

    print(f"\n{'='*58}")
    print(f" Generated {len(generated)}/{len(UTTERANCES)} WAV files")
    print(f"{'='*58}")
    for key, path, dur in generated:
        print(f"  {path.name:<35} {dur:.2f}s")

    # Write a manifest for the stress test to load
    manifest_path = WAV_OUT_DIR / "manifest.json"
    import json

    manifest = {k: str(WAV_OUT_DIR / f"{k}.wav") for k, _, _ in generated}
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"\nManifest: {manifest_path}")


if __name__ == "__main__":
    sys.path.insert(0, str(BACKEND_DIR))
    generate_all()
