"""
Voice Stress Test — S.E.N.T.R.I. (Real Audio Edition)
======================================================
Uses Kokoro-synthesized .wav files for true end-to-end testing:
  MIC (WAV) → WebSocket → ASR → Intent → Reasoning → TTS → Audio back

Prerequisite:
    python tests/generate_test_wavs.py   (run once to create WAV files)

Run:
    cd backend
    .\\venv\\Scripts\\python.exe tests/voice_stress_test.py
"""

import asyncio
import json
import wave
import time
import httpx
import websockets
import sys
import os
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
WS_URL = "ws://localhost:8008/ws/voice"
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = os.environ.get(
    "REASONING_MODEL", "hf.co/HauhauCS/Qwen3.5-4B-Uncensored-HauhauCS-Aggressive:Q4_K_M"
)
WAV_DIR = Path(__file__).parent / "wav"
CHUNK_MS = 30  # ms per audio chunk streamed to server

RESULTS = []

# ── Helpers ───────────────────────────────────────────────────────────────────


def log(scenario: str, msg: str):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] [{scenario}] {msg}"
    print(line)
    RESULTS.append(line)


def load_wav(name: str) -> bytes:
    """Load a WAV file as raw PCM16 bytes."""
    path = WAV_DIR / f"{name}.wav"
    with wave.open(str(path), "rb") as wf:
        assert wf.getnchannels() == 1, f"{name}: expected mono"
        assert wf.getsampwidth() == 2, f"{name}: expected 16-bit"
        assert wf.getframerate() == 16000, f"{name}: expected 16 kHz"
        return wf.readframes(wf.getnframes())


async def send_audio(ws, pcm: bytes, label: str, turn_complete: bool = True):
    """Stream PCM bytes as binary WebSocket frames (30 ms chunks),
    then optionally send the turn_complete signal to trigger ASR."""
    chunk_size = 16000 * 2 * CHUNK_MS // 1000  # bytes per 30 ms
    chunks = [pcm[i : i + chunk_size] for i in range(0, len(pcm), chunk_size)]
    dur = len(pcm) / (16000 * 2)
    log(label, f"Streaming {len(chunks)} chunks ({dur:.2f}s of speech)...")
    for chunk in chunks:
        await ws.send(chunk)
        await asyncio.sleep(CHUNK_MS / 1000)
    if turn_complete:
        # Signal end-of-speech: backend will consume buffer and run ASR
        await ws.send(json.dumps({"type": "turn_complete"}))
        log(label, "  [turn_complete sent]")


async def drain(ws, timeout: float = 8.0, label: str = "") -> list:
    """Collect all incoming messages until silence for `timeout` seconds."""
    msgs = []
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=0.5)
            if isinstance(msg, str):
                data = json.loads(msg)
                msgs.append(data)
                mtype = data.get("type", "?")
                mdata = str(data.get("data") or data.get("message") or "")[:70]
                log(label, f"  [{mtype}] {mdata}")
            else:
                msgs.append({"type": "audio", "bytes": len(msg)})
                log(label, f"  [audio] {len(msg)} bytes")
            deadline = time.time() + timeout  # reset on activity
        except asyncio.TimeoutError:
            break
    return msgs


def summarise(msgs: list) -> dict:
    audio_bytes = sum(m.get("bytes", 0) for m in msgs if m.get("type") == "audio")
    text_chunks = [m for m in msgs if m.get("type") == "text"]
    state_msgs = [m for m in msgs if m.get("type") == "state"]
    transcript = next((m.get("data", "") for m in msgs if m.get("type") == "user"), "")
    return {
        "audio_bytes": audio_bytes,
        "text_chunks": len(text_chunks),
        "states": [m.get("state") for m in state_msgs],
        "transcript": transcript,
        "got_response": audio_bytes > 0 or len(text_chunks) > 0,
    }


# ── Scenarios ─────────────────────────────────────────────────────────────────


async def scenario_1_rapid_bargeins():
    """3 rapid barge-ins while Sentri is responding to a greeting."""
    label = "BARGE-IN x3"
    log(label, "Starting...")
    main_pcm = load_wav("greeting_hello")
    barge_pcm = load_wav("barge_in_stop")

    async with websockets.connect(WS_URL) as ws:
        await send_audio(
            ws, main_pcm, label, turn_complete=False
        )  # no turn_complete — barge-in mid-stream
        await asyncio.sleep(0.3)  # give ASR a moment to start

        for i in range(3):
            log(label, f"  Barge-in #{i+1}")
            await ws.send(barge_pcm[:960])  # 30 ms burst
            await asyncio.sleep(0.05)

        # Send turn_complete after barge-ins so server processes the interrupted audio
        await ws.send(json.dumps({"type": "turn_complete"}))

        msgs = await drain(ws, timeout=6.0, label=label)
        s = summarise(msgs)
        log(label, f"RESULT: {s}")
        return True  # no crash = PASS


async def scenario_2_early_interrupt():
    """Cancel within 200 ms — before TTS has emitted a single byte."""
    label = "EARLY INTERRUPT"
    log(label, "Starting...")
    main_pcm = load_wav("query_name")
    barge_pcm = load_wav("barge_in_stop")

    async with websockets.connect(WS_URL) as ws:
        # Send only 200 ms of the question
        chunk_200ms = main_pcm[: 16000 * 2 * 200 // 1000]
        await ws.send(chunk_200ms)
        await asyncio.sleep(0.2)
        log(label, "Sending barge-in at 200 ms...")
        await ws.send(barge_pcm[:960])
        await ws.send(json.dumps({"type": "turn_complete"}))

        msgs = await drain(ws, timeout=5.0, label=label)
        s = summarise(msgs)
        log(label, f"RESULT: {s}")
        return True


async def scenario_3_last_chunk_interrupt():
    """Interrupt on the very last audio chunk."""
    label = "LAST-CHUNK INTERRUPT"
    log(label, "Starting...")
    main_pcm = load_wav("query_projects")
    barge_pcm = load_wav("barge_in_wait")
    chunk_size = 16000 * 2 * CHUNK_MS // 1000

    chunks = [main_pcm[i : i + chunk_size] for i in range(0, len(main_pcm), chunk_size)]
    async with websockets.connect(WS_URL) as ws:
        for chunk in chunks[:-1]:
            await ws.send(chunk)
            await asyncio.sleep(CHUNK_MS / 1000)
        await ws.send(chunks[-1])
        await asyncio.sleep(0.05)
        log(label, "Barge-in on last chunk...")
        await ws.send(barge_pcm[:960])
        await ws.send(json.dumps({"type": "turn_complete"}))

        msgs = await drain(ws, timeout=6.0, label=label)
        s = summarise(msgs)
        log(label, f"RESULT: {s}")
        return True


async def scenario_4_cancel_restart_cycles():
    """10 real-audio cancel/restart cycles — checks for task leaks."""
    label = "CANCEL/RESTART x10"
    log(label, "Starting...")
    wavs = ["cancel_restart_1", "cancel_restart_2", "cancel_restart_3"]
    errors = 0

    for i in range(10):
        try:
            pcm = load_wav(wavs[i % 3])
            async with websockets.connect(WS_URL) as ws:
                # Send 400 ms then disconnect
                await ws.send(pcm[: 16000 * 2 * 400 // 1000])
                await asyncio.sleep(0.15)
            log(label, f"  Cycle {i+1}/10 OK")
        except Exception as e:
            log(label, f"  Cycle {i+1}/10 ERROR: {e}")
            errors += 1
        await asyncio.sleep(0.2)

    log(label, f"RESULT: errors={errors}/10")
    return errors == 0


async def scenario_5_full_roundtrip():
    """
    Full end-to-end: real speech in → ASR transcript → Sentri reasons → TTS audio out.
    Validates the entire pipeline with real audio.
    """
    label = "FULL ROUNDTRIP"
    log(label, "Starting end-to-end voice conversation...")

    turns = [
        ("greeting_hello", "greeting — expects identity response"),
        ("query_time", "time query — expects quick response"),
        ("query_vram", "VRAM query — expects GPU stats"),
        ("query_name", "name query — expects memory recall"),
        ("compound_morning", "compound — should NOT be IDENTITY_QUERY"),
    ]

    roundtrips = []
    async with websockets.connect(WS_URL) as ws:
        for wav_name, description in turns:
            pcm = load_wav(wav_name)
            log(label, f"\n--- Turn: {description} ({wav_name}) ---")
            t0 = time.time()
            await send_audio(ws, pcm, label)
            msgs = await drain(ws, timeout=20.0, label=label)
            elapsed = time.time() - t0
            s = summarise(msgs)
            s["elapsed_sec"] = round(elapsed, 2)
            s["description"] = description
            roundtrips.append(s)
            log(
                label,
                f"  transcript={repr(s['transcript'][:60])} | "
                f"audio={s['audio_bytes']}B | "
                f"texts={s['text_chunks']} | "
                f"elapsed={s['elapsed_sec']}s",
            )
            await asyncio.sleep(1.0)

    got_any_response = any(r["got_response"] for r in roundtrips)
    got_transcripts = [r for r in roundtrips if r["transcript"]]
    log(
        label,
        f"\nRESULT: {len(got_transcripts)}/{len(turns)} turns transcribed, "
        f"any_response={got_any_response}",
    )
    return got_any_response


# ── Main ──────────────────────────────────────────────────────────────────────


async def main():
    print("=" * 60)
    print(" S.E.N.T.R.I. Voice Stress Test — Real Audio Edition")
    print(f" Target: {WS_URL}")
    print(f" WAV dir: {WAV_DIR}")
    print("=" * 60)

    # Check backend
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get("http://localhost:8008/")
            print(f"Backend: {r.status_code} {r.text[:50]}")
    except Exception as e:
        print(f"[ERROR] Backend not reachable: {e}")
        sys.exit(1)

    # Check WAV files exist
    required = [
        "greeting_hello",
        "query_name",
        "query_projects",
        "query_time",
        "query_vram",
        "barge_in_stop",
        "barge_in_wait",
        "compound_morning",
        "cancel_restart_1",
        "cancel_restart_2",
        "cancel_restart_3",
    ]
    missing = [n for n in required if not (WAV_DIR / f"{n}.wav").exists()]
    if missing:
        print(f"[ERROR] Missing WAV files: {missing}")
        print("Run:  .\\venv\\Scripts\\python tests/generate_test_wavs.py")
        sys.exit(1)
    print(f"WAV files: {len(required)} found\n")

    scenarios = [
        ("1. Rapid barge-ins x3", scenario_1_rapid_bargeins),
        ("2. Early interrupt (200 ms)", scenario_2_early_interrupt),
        ("3. Last-chunk interrupt", scenario_3_last_chunk_interrupt),
        ("4. Cancel/restart x10", scenario_4_cancel_restart_cycles),
        ("5. Full end-to-end round-trip", scenario_5_full_roundtrip),
    ]

    summary = []
    for name, fn in scenarios:
        print(f"\n{'-'*60}")
        print(f" {name}")
        print("-" * 60)
        try:
            ok = await fn()
            status = "PASS" if ok else "FAIL"
        except Exception as e:
            status = f"ERROR: {e}"
        summary.append((name, status))
        await asyncio.sleep(1.5)

    print(f"\n{'='*60}")
    print(" SUMMARY")
    print("=" * 60)
    for name, status in summary:
        icon = "OK " if status == "PASS" else "ERR"
        print(f"  [{icon}] {name}: {status}")

    # Write results
    out = r"c:\Users\JARVIS\Desktop\SENTRI\30 Bugs\voice_stress_results.md"
    with open(out, "w", encoding="utf-8") as f:
        f.write("# Voice Stress Test Results — Real Audio Edition\n\n")
        f.write(f"**Run:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("**Audio:** Kokoro TTS (af_sarah, en-gb, 16 kHz PCM16)\n\n")
        f.write("## Summary\n\n| Scenario | Result |\n|---|---|\n")
        for name, status in summary:
            icon = "OK" if status == "PASS" else "FAIL"
            f.write(f"| {name} | {icon} {status} |\n")
        f.write("\n## Full Log\n\n```\n" + "\n".join(RESULTS) + "\n```\n")
    print(f"\nResults: {out}")


if __name__ == "__main__":
    asyncio.run(main())
