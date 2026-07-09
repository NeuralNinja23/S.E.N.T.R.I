import asyncio
import logging
import numpy as np
from abc import ABC, abstractmethod
from typing import AsyncGenerator
from app.runtime.model_runtime import inference_runtime_manager

logger = logging.getLogger("tts_provider")

class TTSProvider(ABC):
    """
    Interface for Text-to-Speech synthesis engines.
    """
    @abstractmethod
    async def synthesize(self, text: str) -> AsyncGenerator[bytes, None]:
        """
        Synthesizes a text chunk into raw PCM16 audio bytes.
        """
        pass

class KokoroTTSProvider(TTSProvider):
    """
    Local Kokoro ONNX Speech Synthesis provider.
    """
    def __init__(self, voice_name: str = "af_sarah"):
        self.voice_name = voice_name

    async def synthesize(self, text: str) -> AsyncGenerator[bytes, None]:
        if not text or not text.strip():
            return

        def _synthesize():
            kokoro = inference_runtime_manager.kokoro_model
            if not kokoro:
                logger.error("Kokoro ONNX model is not loaded in InferenceRuntimeManager.")
                return None

            try:
                # Kokoro ONNX yields float32 audio samples and sample rate (usually 24000 Hz)
                samples, sample_rate = kokoro.create(
                    text,
                    voice=self.voice_name,
                    speed=1.0,
                    lang="en-us"
                )
                
                # Convert float32 array normalized to [-1.0, 1.0] to 16-bit signed PCM
                pcm16 = (samples * 32767.0).astype(np.int16)
                return pcm16.tobytes()
            except Exception as e:
                logger.error(f"Failed inside Kokoro ONNX runtime generator: {e}")
                return None

        try:
            pcm_bytes = await asyncio.to_thread(_synthesize)
            if pcm_bytes:
                yield pcm_bytes
        except Exception as e:
            logger.error(f"Kokoro synthesis execution thread failed for text '{text}': {e}")
            return
