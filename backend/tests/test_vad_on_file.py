import os
import sys
import numpy as np
import wave
import onnxruntime as ort

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.local.vad_service import VADService

def run_diagnostics():
    wav_path = "debug_speech.wav"
    if not os.path.exists(wav_path):
        print(f"Error: {wav_path} not found.")
        return

    with wave.open(wav_path, "rb") as wf:
        n_channels = wf.getnchannels()
        samp_width = wf.getsampwidth()
        frame_rate = wf.getframerate()
        n_frames = wf.getnframes()
        raw_bytes = wf.readframes(n_frames)
        
    print("=== Audio File Diagnostics ===")
    print(f"Channels: {n_channels}")
    print(f"Sample Width: {samp_width} bytes ({samp_width*8} bits)")
    print(f"Frame Rate: {frame_rate} Hz")
    print(f"Total Frames: {n_frames}")
    print(f"Total Duration: {n_frames / frame_rate:.2f} seconds")
    print(f"Total Bytes: {len(raw_bytes)}")
    
    # Parse audio values
    audio_data = np.frombuffer(raw_bytes, dtype=np.int16)
    print(f"Min amplitude: {audio_data.min()}")
    print(f"Max amplitude: {audio_data.max()}")
    print(f"Mean (DC Offset): {audio_data.mean():.2f}")
    print(f"Standard deviation (volume): {audio_data.std():.2f}")
    
    print("\n=== Simulating Stateful VAD Chunk Processing ===")
    vad = VADService(16000)
    
    # Process in 32ms chunks (512 samples / 1024 bytes)
    chunk_size_bytes = 1024
    total_chunks = len(raw_bytes) // chunk_size_bytes
    
    speech_detected_count = 0
    highest_prob = 0.0
    
    for i in range(total_chunks):
        chunk = raw_bytes[i * chunk_size_bytes : (i + 1) * chunk_size_bytes]
        
        # Calculate max amp of this chunk
        chunk_amp = np.abs(np.frombuffer(chunk, dtype=np.int16)).max()
        
        # Get VAD probability
        prob = vad.is_speech(chunk)
        if prob > highest_prob:
            highest_prob = prob
            
        if prob > 0.25:
            speech_detected_count += 1
            print(f"Chunk {i:03d} (Time {i*0.032:.2f}s): Max Amp={chunk_amp:5d} -> Speech detected! Prob={prob:.4f}")
            
    print(f"\nStateful VAD Summary:")
    print(f"- Total 32ms chunks: {total_chunks}")
    print(f"- Highest speech probability reached: {highest_prob:.4f}")
    print(f"- Chunks exceeding 0.25 threshold: {speech_detected_count}")
    
    print("\n=== Simulating Stateful VAD with Gain Multiplier (2.0x) ===")
    vad.reset()
    highest_prob_gain = 0.0
    speech_detected_count_gain = 0
    
    for i in range(total_chunks):
        chunk = raw_bytes[i * chunk_size_bytes : (i + 1) * chunk_size_bytes]
        audio_array = np.frombuffer(chunk, dtype=np.int16)
        
        # Apply 2x gain, clip to int16 boundaries
        boosted_audio = np.clip(audio_array.astype(np.int32) * 2, -32768, 32767).astype(np.int16)
        boosted_bytes = boosted_audio.tobytes()
        
        chunk_amp = np.abs(boosted_audio).max()
        prob = vad.is_speech(boosted_bytes)
        
        if prob > highest_prob_gain:
            highest_prob_gain = prob
            
        if prob > 0.25:
            speech_detected_count_gain += 1
            print(f"Gain Chunk {i:03d}: Max Amp={chunk_amp:5d} -> Speech detected! Prob={prob:.4f}")
            
    print(f"Gain Stateful VAD Summary:")
    print(f"- Highest speech probability reached: {highest_prob_gain:.4f}")
    print(f"- Chunks exceeding 0.25 threshold: {speech_detected_count_gain}")

if __name__ == "__main__":
    run_diagnostics()
