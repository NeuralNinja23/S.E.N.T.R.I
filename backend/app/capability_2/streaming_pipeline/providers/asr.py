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
        # Resilience test hook: check for mock_asr.txt file
        try:
            import os
            from pathlib import Path
            project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
            mock_file = project_root / "Docs" / "Tests" / "System Resilience" / "mock_asr.txt"
            if not mock_file.exists():
                mock_file = Path("Docs/Tests/System Resilience/mock_asr.txt")
            if mock_file.exists():
                text = mock_file.read_text(encoding="utf-8").strip()
                return text

        except Exception:
            pass

        if not pcm_bytes:
            return ""

        try:
            # Convert 16kHz PCM16 bytes directly to float32 numpy array normalized to [-1.0, 1.0]
            audio_array = (
                np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            )
        except Exception as e:
            logger.error(f"Failed to convert PCM bytes to float32 array: {e}")
            return ""

        def _transcribe():
            whisper = inference_runtime_manager.whisper_model
            if not whisper:
                logger.error(
                    "Faster-Whisper model is not initialized inside InferenceRuntimeManager."
                )
                return ""

            # Bug #23: Removed [ASR DEBUG] amplitude/diagnostic logging block — was polluting production logs
            # beam_size=1 = greedy decoding. Much faster for conversational ASR.
            # Accuracy drop is minimal vs. the latency gain.
            from app.config import (
                ASR_LANGUAGE,
            )  # Bug #10: language from config, default "en"

            segments, info = whisper.transcribe(
                audio_array, beam_size=1, language=ASR_LANGUAGE
            )
            text = "".join([segment.text for segment in segments]).strip()
            return text

        try:
            text = await asyncio.to_thread(_transcribe)
            return text
        except Exception as e:
            logger.error(f"Faster-Whisper transcription failed: {e}")
            return ""
