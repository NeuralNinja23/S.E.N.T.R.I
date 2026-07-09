import audioop
from app.services.logger import get_logger

logger = get_logger("vad_service")

class VADService:
    def __init__(self, sample_rate: int = 16000, threshold: int = 1000):
        self.sample_rate = sample_rate
        self.threshold = threshold
        logger.info(f"Initialized high-performance RMS-based VAD (threshold={threshold})")

    def reset(self):
        """No state needs to be reset for RMS VAD."""
        pass

    def is_speech(self, pcm_bytes: bytes) -> float:
        """
        Processes a single audio chunk (pcm_bytes).
        Audio must be 16-bit mono PCM.
        Returns 1.0 if RMS exceeds threshold (speech), else 0.0 (silence).
        """
        if not pcm_bytes:
            return 0.0
            
        try:
            rms = audioop.rms(pcm_bytes, 2)
            if rms > self.threshold:
                return 1.0
            return 0.0
        except Exception as e:
            logger.error(f"RMS VAD process error: {e}")
            return 0.0
