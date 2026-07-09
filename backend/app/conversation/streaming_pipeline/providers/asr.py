import asyncio
import logging
import numpy as np
from abc import ABC, abstractmethod
from app.runtime.model_runtime import inference_runtime_manager

logger = logging.getLogger("asr_provider")

class ASRProvider(ABC):
    """
    Interface for Speech-to-Text transcription engines.
    """
    @abstractmethod
    async def transcribe(self, pcm_bytes: bytes) -> str:
        """
        Transcribes raw PCM16 audio bytes in-memory and returns the text transcript.
        """
        pass

class FasterWhisperASRProvider(ASRProvider):
    """
    GPU-accelerated Faster-Whisper ASR provider performing transcription entirely in-memory.
    """
    def __init__(self):
        pass

    async def transcribe(self, pcm_bytes: bytes) -> str:
        if not pcm_bytes:
            return ""

        try:
            # Convert 16kHz PCM16 bytes directly to float32 numpy array normalized to [-1.0, 1.0]
            audio_array = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        except Exception as e:
            logger.error(f"Failed to convert PCM bytes to float32 array: {e}")
            return ""

        def _transcribe():
            whisper = inference_runtime_manager.whisper_model
            if not whisper:
                logger.error("Faster-Whisper model is not initialized inside InferenceRuntimeManager.")
                return ""

            # === DIAGNOSTIC LOGGING ===
            duration_s = len(audio_array) / 16000.0
            logger.info(
                f"[ASR DEBUG] Audio stats: "
                f"samples={len(audio_array)}, duration={duration_s:.2f}s, "
                f"dtype={audio_array.dtype}, shape={audio_array.shape}, "
                f"min={audio_array.min():.4f}, max={audio_array.max():.4f}, "
                f"mean={audio_array.mean():.6f}"
            )
            # === END DIAGNOSTIC ===

            # beam_size=1 = greedy decoding. Much faster for conversational ASR.
            # Accuracy drop is minimal vs. the latency gain.
            segments, info = whisper.transcribe(audio_array, beam_size=1, language="en")
            text = "".join([segment.text for segment in segments]).strip()
            return text

        try:
            text = await asyncio.to_thread(_transcribe)
            return text
        except Exception as e:
            logger.error(f"Faster-Whisper transcription failed: {e}")
            return ""
