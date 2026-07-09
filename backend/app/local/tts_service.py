import os
import re
import urllib.request
import threading
import numpy as np
from app.config import TTS_SPEAKER_VOICE
from app.services.logger import get_logger

logger = get_logger("tts_service")

# Inject CUDA and cuDNN DLL directories so onnxruntime-gpu can locate them on Windows
_CUDA_BIN = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4\bin"
_CUDNN_BIN = r"C:\Program Files\NVIDIA\CUDNN\v9.24\bin\12.9\x64"
for _dll_path in [_CUDA_BIN, _CUDNN_BIN]:
    if os.path.isdir(_dll_path) and _dll_path not in os.environ.get("PATH", ""):
        os.add_dll_directory(_dll_path)
        os.environ["PATH"] = _dll_path + os.pathsep + os.environ.get("PATH", "")
        logger.info(f"[TTS] Injected DLL path: {_dll_path}")


MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"

class TTSService:
    _kokoro = None
    _lock = threading.Lock()
    
    # Path where we download and cache Kokoro models
    _cache_dir = os.path.join(os.path.dirname(__file__), "resources")
    _model_path = os.path.join(_cache_dir, "kokoro-v1.0.onnx")
    _voices_path = os.path.join(_cache_dir, "voices-v1.0.bin")

    @classmethod
    def _ensure_model_files(cls):
        """Downloads the ONNX model and voices file if they do not exist."""
        if not os.path.exists(cls._cache_dir):
            os.makedirs(cls._cache_dir, exist_ok=True)
            
        def download_file(url, path):
            logger.info(f"Downloading {url} to {path}...")
            # Download file using urllib
            urllib.request.urlretrieve(url, path)
            logger.info(f"Downloaded {path} successfully.")

        if not os.path.exists(cls._model_path):
            download_file(MODEL_URL, cls._model_path)
            
        if not os.path.exists(cls._voices_path):
            download_file(VOICES_URL, cls._voices_path)

    @classmethod
    def _get_kokoro(cls):
        """Returns the initialized Kokoro ONNX instance (cached singleton)."""
        if cls._kokoro is None:
            with cls._lock:
                if cls._kokoro is None:
                    cls._ensure_model_files()
                    from kokoro_onnx import Kokoro
                    try:
                        import onnxruntime as ort
                        available_providers = ort.get_available_providers()
                        if "CUDAExecutionProvider" in available_providers:
                            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
                            logger.info("Initializing Kokoro TTS engine on ONNX Runtime CUDA (GPU)...")
                        else:
                            providers = ["CPUExecutionProvider"]
                            logger.info("Initializing Kokoro TTS engine on ONNX Runtime CPU...")
                        cls._kokoro = Kokoro(cls._model_path, cls._voices_path)
                        logger.info(f"Kokoro TTS engine initialized with providers: {providers}")
                    except Exception as e:
                        logger.error(f"Failed to initialize Kokoro engine: {e}")
                        raise e
        return cls._kokoro

    @classmethod
    def generate_audio_stream(cls, text: str):
        """
        Splits text by sentence and yields raw 24kHz 16-bit Mono PCM bytes for streaming response.
        """
        if not text:
            return

        try:
            kokoro = cls._get_kokoro()
        except Exception as init_err:
            logger.error(f"Cannot initialize TTS engine, skipping generation: {init_err}")
            return
        
        # Split text into sentences using simple regex
        sentences = re.split(r'(?<=[.!?])\s+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        for sentence in sentences:
            try:
                logger.info(f"Synthesizing sentence: '{sentence}'")
                samples, sample_rate = kokoro.create(
                    sentence,
                    voice=TTS_SPEAKER_VOICE,
                    speed=1.0,
                    lang="en-us"
                )
                
                # Convert float32 array normalized to [-1.0, 1.0] to 16-bit signed PCM
                pcm16_samples = (samples * 32767.0).astype(np.int16)
                yield pcm16_samples.tobytes()
            except Exception as e:
                logger.error(f"Error synthesizing sentence '{sentence}': {e}")
