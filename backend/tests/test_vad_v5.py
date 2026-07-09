import numpy as np
import onnxruntime as ort
import wave
import urllib.request
import os

def run_v5_test():
    # Try Hugging Face or Snakers4 master URLs
    urls_to_try = [
        "https://huggingface.co/onnx-community/silero-vad/resolve/main/onnx/silero_vad.onnx",
        "https://github.com/snakers4/silero-vad/raw/master/files/silero_vad.onnx"
    ]
    v5_path = "tests/silero_vad_v5.onnx"
    
    if not os.path.exists(v5_path):
        for url in urls_to_try:
            try:
                print(f"Trying download from {url}...")
                urllib.request.urlretrieve(url, v5_path)
                print("Download succeeded!")
                break
            except Exception as e:
                print(f"Failed to download from {url}: {e}")
        
        if not os.path.exists(v5_path):
            print("Error: Could not download v5 model from any URL.")
            return
        
    wav_path = "debug_speech.wav"
    if not os.path.exists(wav_path):
        print("debug_speech.wav not found.")
        return
        
    with wave.open(wav_path, "rb") as wf:
        raw_bytes = wf.readframes(wf.getnframes())
        
    audio = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    
    print("\n=== Inspecting VAD v5 Model ===")
    session = ort.InferenceSession(v5_path)
    print("Inputs:")
    for i in session.get_inputs():
        print(f"- {i.name}: shape={i.shape}, type={i.type}")
    print("Outputs:")
    for o in session.get_outputs():
        print(f"- {o.name}: shape={o.shape}, type={o.type}")
        
    # Check stateful runs (correct state update for v5)
    # v5 state shape: (2, batch_size, 64)
    state = np.zeros((2, 1, 64), dtype=np.float32)
    chunk_size = 512
    total_chunks = len(audio) // chunk_size
    max_prob = 0.0
    speech_detected_count = 0
    
    print("\nStateful test with VAD v5:")
    for i in range(total_chunks):
        chunk = audio[i * chunk_size : (i + 1) * chunk_size]
        audio_input = chunk[np.newaxis, :]
        sr = np.array(16000, dtype=np.int64)
        
        outputs = session.run(None, {'input': audio_input, 'sr': sr, 'state': state})
        prob = float(outputs[0][0][0])
        state = outputs[1] # Pass state along
        
        if prob > max_prob:
            max_prob = prob
            
        if prob > 0.25:
            speech_detected_count += 1
            print(f"Chunk {i:03d}: Stateful prob: {prob:.4f} (Max Amp={np.abs(chunk).max()*32768:.0f})")
            
    print(f"Max stateful probability with v5: {max_prob:.4f}")
    print(f"Chunks exceeding 0.25 threshold with v5: {speech_detected_count}")

if __name__ == "__main__":
    run_v5_test()
