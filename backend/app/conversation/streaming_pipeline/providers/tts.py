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

        kokoro = inference_runtime_manager.kokoro_model
        if not kokoro:
            logger.error("Kokoro ONNX model is not loaded in InferenceRuntimeManager.")
            return

        try:
            # Consume Kokoro's native async create_stream generator
            async for samples, sample_rate in kokoro.create_stream(
                text,
                voice=self.voice_name,
                speed=1.0,
                lang="en-us"
            ):
                if len(samples) > 0:
                    # Convert float32 array normalized to [-1.0, 1.0] to 16-bit signed PCM
                    pcm16 = (samples * 32767.0).astype(np.int16)
                    yield pcm16.tobytes()
        except Exception as e:
            logger.error(f"Kokoro stream synthesis failed for text '{text}': {e}")
            return

