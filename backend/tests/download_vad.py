import urllib.request
import os
import onnxruntime as ort
import numpy as np
import wave

def download_and_test():
    url = "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"
    dest = "tests/silero_vad_fresh.onnx"
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    req = urllib.request.Request(url, headers=headers)
    
    print(f"Downloading from {url}...")
    try:
        with urllib.request.urlopen(req) as response:
            with open(dest, "wb") as f:
                f.write(response.read())
        print(f"Downloaded fresh ONNX! Size: {os.path.getsize(dest)} bytes")
    except Exception as e:
        print(f"Download failed: {e}")
        return

    # Load and test fresh ONNX
    try:
        session = ort.InferenceSession(dest)
        
        # Load chunk 23
        with wave.open("debug_speech.wav", "rb") as wf:
            raw_bytes = wf.readframes(wf.getnframes())
        audio = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        
        chunk = audio[23*512:24*512][np.newaxis, :]
        state = np.zeros((2, 1, 128), dtype=np.float32)
        sr = np.array(16000, dtype=np.int64)
        
        outputs = session.run(None, {'input': chunk, 'sr': sr, 'state': state})
        print(f"Fresh model VAD prob for chunk 23: {outputs[0][0][0]:.6f}")
    except Exception as e:
        print(f"Error testing model: {e}")

if __name__ == "__main__":
    download_and_test()
