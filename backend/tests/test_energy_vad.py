import wave
import audioop
import os


def test_energy_vad():
    wav_path = "debug_speech.wav"
    if not os.path.exists(wav_path):
        print("debug_speech.wav not found.")
        return

    with wave.open(wav_path, "rb") as wf:
        raw_bytes = wf.readframes(wf.getnframes())

    # Process in 32ms chunks (1024 bytes)
    chunk_size = 1024
    total_chunks = len(raw_bytes) // chunk_size

    threshold = 800  # RMS threshold
    is_user_speaking = False
    silence_chunks = 0

    speech_starts = []
    speech_ends = []

    for i in range(total_chunks):
        chunk = raw_bytes[i * chunk_size : (i + 1) * chunk_size]
        rms = audioop.rms(chunk, 2)

        if rms > threshold:
            if not is_user_speaking:
                is_user_speaking = True
                speech_starts.append(i * 0.032)
                print(f"[{i * 0.032:.2f}s] Speech DETECTED (RMS={rms})")
            silence_chunks = 0
        else:
            if is_user_speaking:
                silence_chunks += 1
                if silence_chunks >= 38:  # 1.2s of silence
                    is_user_speaking = False
                    speech_ends.append(i * 0.032)
                    print(
                        f"[{i * 0.032:.2f}s] Silence threshold met. Speech COMPLETED."
                    )

    print("\n--- Energy VAD Summary ---")
    print(f"Speech segments detected: {len(speech_starts)}")
    for start, end in zip(
        speech_starts,
        speech_ends
        + ([total_chunks * 0.032] if len(speech_starts) > len(speech_ends) else []),
    ):
        print(f"- From {start:.2f}s to {end:.2f}s (Duration: {end - start:.2f}s)")


if __name__ == "__main__":
    test_energy_vad()
