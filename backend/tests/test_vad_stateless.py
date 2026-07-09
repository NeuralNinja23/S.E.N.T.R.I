import numpy as np
import onnxruntime as ort
import wave
import os

def run_stateless_test():
    wav_path = "debug_speech.wav"
    if not os.path.exists(wav_path):
        print("debug_speech.wav not found.")
        return
        
    with wave.open(wav_path, "rb") as wf:
        raw_bytes = wf.readframes(wf.getnframes())
        
    audio = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    
    session = ort.InferenceSession('app/local/resources/silero_vad.onnx')
    
    # Check stateless runs
    chunk_size = 512
    total_chunks = len(audio) // chunk_size
    
    print(f"Stateless test on {total_chunks} chunks:")
    
    max_prob = 0.0
    for i in range(total_chunks):
        chunk = audio[i * chunk_size : (i + 1) * chunk_size]
        audio_input = chunk[np.newaxis, :]
        
        # Fresh zero state every time
        state = np.zeros((2, 1, 128), dtype=np.float32)
        sr = np.array(16000, dtype=np.int64)
        
        outputs = session.run(None, {'input': audio_input, 'sr': sr, 'state': state})
        prob = float(outputs[0][0][0])
        if prob > max_prob:
            max_prob = prob
            
        if prob > 0.01:
            print(f"Chunk {i:03d} stateless prob: {prob:.4f} (Max Amp={np.abs(chunk).max()*32768:.0f})")
            
    print(f"Max stateless probability: {max_prob:.4f}")

    # Check stateful runs (correct state update)
    print("\nStateful test with correct state update:")
    state = np.zeros((2, 1, 128), dtype=np.float32)
    max_prob_stateful = 0.0
    
    for i in range(total_chunks):
        chunk = audio[i * chunk_size : (i + 1) * chunk_size]
        audio_input = chunk[np.newaxis, :]
        sr = np.array(16000, dtype=np.int64)
        
        outputs = session.run(None, {'input': audio_input, 'sr': sr, 'state': state})
        prob = float(outputs[0][0][0])
        state = outputs[1] # Pass state along
        
        if prob > max_prob_stateful:
            max_prob_stateful = prob
            
        if prob > 0.01:
            print(f"Chunk {i:03d} stateful prob: {prob:.4f}")
            
    print(f"Max stateful probability: {max_prob_stateful:.4f}")

if __name__ == "__main__":
    run_stateless_test()
