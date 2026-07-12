import gc
import os
import logging
import asyncio
import httpx
import numpy as np
from enum import Enum
from pathlib import Path

logger = logging.getLogger("model_runtime")

class ModelState(str, Enum):
    UNLOADED = "UNLOADED"
    LOADING = "LOADING"
    READY = "READY"
    FAILED = "FAILED"
    UNLOADING = "UNLOADING"

class InferenceRuntimeManager:
    """
    Manages in-memory singletons and lifecycle allocations for local models 
    (Faster-Whisper ASR & Kokoro ONNX TTS) using explicit model states.
    """
    def __init__(self):
        self.state: ModelState = ModelState.UNLOADED
        self.whisper_model = None
        self.kokoro_model = None

    async def start(self):
        """
        Loads the ASR and TTS models into GPU VRAM (or CPU) on application startup.
        Downloads model weights automatically if they are not already cached.
        """
        if self.state == ModelState.READY:
            logger.info("Inference models are already loaded and ready.")
            return

        self.state = ModelState.LOADING
        logger.info("[RUNTIME] Initializing local speech models...")

        try:
            # 1. Load Faster-Whisper Model in-memory (GPU if available)
            def load_whisper():
                import onnxruntime as ort
                from faster_whisper import WhisperModel
                
                # Check CUDA availability via ONNX runtime to avoid PyTorch dependency
                available_providers = ort.get_available_providers()
                if "CUDAExecutionProvider" in available_providers:
                    device = "cuda"
                    compute_type = "float16"
                else:
                    device = "cpu"
                    compute_type = "int8"
                
                logger.info(f"[RUNTIME] Loading Faster-Whisper (base) on {device} ({compute_type})...")
                try:
                    return WhisperModel("base", device=device, compute_type=compute_type)
                except Exception as err:
                    logger.warning(f"[RUNTIME] Failed loading Faster-Whisper on {device}: {err}. Falling back to CPU.")
                    return WhisperModel("base", device="cpu", compute_type="int8")

            self.whisper_model = await asyncio.to_thread(load_whisper)

            # 2. Load Kokoro ONNX TTS Model in-memory (GPU via ONNX Runtime CUDA EP if available)
            def load_kokoro():
                import onnxruntime as ort
                from kokoro_onnx import Kokoro
                import urllib.request

                # Paths relative to backend
                resources_dir = Path(__file__).resolve().parent.parent / "conversation" / "resources"
                resources_dir.mkdir(parents=True, exist_ok=True)

                model_path = resources_dir / "kokoro-v1.0.onnx"
                voices_path = resources_dir / "voices-v1.0.bin"

                MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
                VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"

                # Trigger automatic downloads if files do not exist
                if not model_path.exists():
                    logger.info(f"[RUNTIME] Kokoro ONNX model missing. Downloading from {MODEL_URL}...")
                    urllib.request.urlretrieve(MODEL_URL, str(model_path))
                if not voices_path.exists():
                    logger.info(f"[RUNTIME] Kokoro voices data missing. Downloading from {VOICES_URL}...")
                    urllib.request.urlretrieve(VOICES_URL, str(voices_path))

                # Check ONNX providers
                def is_cudnn_available() -> bool:
                    import os
                    from pathlib import Path
                    for path_dir in os.environ.get("PATH", "").split(os.pathsep):
                        try:
                            p = Path(path_dir)
                            if p.exists() and p.is_dir() and list(p.glob("cudnn*.dll")):
                                return True
                        except Exception:
                            continue
                    cuda_path = os.environ.get("CUDA_PATH", "")
                    if cuda_path:
                        try:
                            p = Path(cuda_path) / "bin"
                            if p.exists() and p.is_dir() and list(p.glob("cudnn*.dll")):
                                return True
                        except Exception:
                            pass
                    return False

                available_providers = ort.get_available_providers()
                if "CUDAExecutionProvider" in available_providers and is_cudnn_available():
                    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
                    logger.info("[RUNTIME] Initializing Kokoro TTS with CUDA Execution Provider...")
                    try:
                        inf_sess = ort.InferenceSession(str(model_path), providers=providers)
                        return Kokoro.from_session(inf_sess, str(voices_path))
                    except Exception as err:
                        logger.warning(f"[RUNTIME] Failed loading Kokoro TTS on CUDA: {err}. Falling back to CPU.")
                
                logger.info("[RUNTIME] Initializing Kokoro TTS with CPU Execution Provider...")
                providers = ["CPUExecutionProvider"]
                inf_sess = ort.InferenceSession(str(model_path), providers=providers)
                return Kokoro.from_session(inf_sess, str(voices_path))

            self.kokoro_model = await asyncio.to_thread(load_kokoro)

            # 3. Warm-up Faster-Whisper: run dummy transcription to pre-compile CUDA kernels
            def warmup_whisper():
                try:
                    logger.info("[RUNTIME] Warming up Faster-Whisper CUDA kernels...")
                    silence = np.zeros(16000, dtype=np.float32)  # 1 second of silence
                    segments, _ = self.whisper_model.transcribe(silence, language="en")
                    list(segments)  # Consume the generator to trigger compilation
                    logger.info("[RUNTIME] Faster-Whisper warmup complete.")
                except Exception as e:
                    logger.warning(f"[RUNTIME] Faster-Whisper warmup failed (non-fatal): {e}")

            await asyncio.to_thread(warmup_whisper)

            # 4. Warm-up Kokoro TTS: run a dummy synthesis to pre-compile ONNX CUDA kernels
            def warmup_kokoro():
                try:
                    logger.info("[RUNTIME] Warming up Kokoro TTS CUDA kernels...")
                    self.kokoro_model.create("warmup", voice="bm_george", speed=1.0, lang="en-us")
                    logger.info("[RUNTIME] Kokoro TTS warmup complete.")
                except Exception as e:
                    logger.warning(f"[RUNTIME] Kokoro warmup failed (non-fatal): {e}")

            await asyncio.to_thread(warmup_kokoro)

            # 4. Warm-up Ollama: send a minimal dummy prompt to force model into GPU VRAM
            async def warmup_ollama():
                from app.config import REASONING_MODEL
                try:
                    logger.info(f"[RUNTIME] Warming up Ollama model '{REASONING_MODEL}' into VRAM...")
                    async with httpx.AsyncClient(timeout=120.0) as client:
                        await client.post(
                            "http://127.0.0.1:11434/api/generate",
                            json={"model": REASONING_MODEL, "prompt": "hi", "stream": False, "options": {"num_predict": 1}}
                        )
                    logger.info("[RUNTIME] Ollama model warmup complete.")
                except Exception as e:
                    logger.warning(f"[RUNTIME] Ollama warmup failed (non-fatal): {e}")

            # Fire Ollama warmup as a background task — do NOT await it.
            # This lets uvicorn start accepting connections in ~13s while
            # the 9B model loads silently into VRAM in the background.
            asyncio.create_task(warmup_ollama())

            self.state = ModelState.READY
            logger.info("[RUNTIME] ASR and TTS models ready. Ollama warming up in background.")

        except Exception as e:
            logger.error(f"[RUNTIME] Failed to load local speech models: {e}", exc_info=True)
            self.state = ModelState.FAILED
            self.whisper_model = None
            self.kokoro_model = None

    def stop(self):
        """
        Unloads models from memory and invokes garbage collection/CUDA cache clearing to release VRAM.
        """
        if self.state == ModelState.UNLOADED:
            return

        self.state = ModelState.UNLOADING
        logger.info("[RUNTIME] Unloading local models from memory...")

        self.whisper_model = None
        self.kokoro_model = None

        # Force garbage collection and empty CUDA cache
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                logger.info("[RUNTIME] CUDA VRAM cache cleared successfully.")
        except ImportError:
            pass

        self.state = ModelState.UNLOADED
        logger.info("[RUNTIME] Inference runtime stopped and memory released.")

# Expose a singleton instance for global runtime management
inference_runtime_manager = InferenceRuntimeManager()
