import os
import threading
import numpy as np
from app.config import ASR_MODEL_SIZE
from app.services.logger import get_logger

logger = get_logger("asr_service")

# Inject CUDA and cuDNN DLL directories so ctranslate2 can locate them on Windows
_CUDA_BIN = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4\bin"
_CUDNN_BIN = r"C:\Program Files\NVIDIA\CUDNN\v9.24\bin\12.9\x64"
for _dll_path in [_CUDA_BIN, _CUDNN_BIN]:
    if os.path.isdir(_dll_path) and _dll_path not in os.environ.get("PATH", ""):
        os.add_dll_directory(_dll_path)
        os.environ["PATH"] = _dll_path + os.pathsep + os.environ.get("PATH", "")
        logger.info(f"[ASR] Injected DLL path: {_dll_path}")


class ASRService:
    _model = None
    _lock = threading.Lock()

    @classmethod
    def _get_model(cls):
        """Initialise and cache the WhisperModel instance (thread-safe)."""
        if cls._model is None:
            with cls._lock:
                if cls._model is None:
                    from faster_whisper import WhisperModel
                    import ctranslate2
                    # Auto-detect CUDA availability
                    cuda_available = bool(ctranslate2.get_supported_compute_types("cuda"))
                    device = "cuda" if cuda_available else "cpu"
                    compute_type = "float16" if device == "cuda" else "int8"
                    logger.info(f"Loading local WhisperModel (size: '{ASR_MODEL_SIZE}') on {device.upper()} [{compute_type}]...")
                    try:
                        cls._model = WhisperModel(
                            ASR_MODEL_SIZE,
                            device=device,
                            compute_type=compute_type,
                            local_files_only=True
                        )
                        logger.info(f"WhisperModel loaded successfully on {device.upper()}.")
                    except Exception as e:
                        logger.warning(f"CUDA init failed ({e}), falling back to CPU.")
                        cls._model = WhisperModel(ASR_MODEL_SIZE, device="cpu", compute_type="int8", local_files_only=True)
                        logger.info("WhisperModel loaded on CPU (fallback).")
        return cls._model

    @classmethod
    def transcribe(cls, pcm_bytes: bytes) -> str:
        """
        Transcribes raw 16-bit 16kHz PCM audio bytes into text.
        """
        if not pcm_bytes:
            return ""
            
        try:
            model = cls._get_model()
            
            # Convert 16-bit PCM bytes to float32 numpy array normalized to [-1.0, 1.0]
            audio_array = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            
            # Run transcription
            with cls._lock:
                logger.info(f"Transcribing audio buffer of {len(pcm_bytes)} bytes locally...")
                segments, info = model.transcribe(audio_array, beam_size=5)
                
                text_segments = []
                for segment in segments:
                    text_segments.append(segment.text)
                
            transcription = "".join(text_segments).strip()
            logger.info(f"Transcription complete: '{transcription}'")
            return transcription
        except Exception as e:
            logger.error(f"Error in local ASR transcription: {e}")
            return ""
