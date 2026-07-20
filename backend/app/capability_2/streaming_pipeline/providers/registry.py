from app.capability_2.streaming_pipeline.providers.asr import (
    ASRProvider,
    FasterWhisperASRProvider,
)
from app.capability_2.streaming_pipeline.providers.reasoning import (
    ReasoningProvider,
    OllamaReasoningProvider,
)
from app.capability_2.streaming_pipeline.providers.tts import (
    TTSProvider,
    KokoroTTSProvider,
)


class ProviderRegistry:
    """
    Central factory registry managing the resolution and initialization of
    ASR, Reasoning, and TTS provider drivers.
    """

    @staticmethod
    def get_asr(provider_id: str, **kwargs) -> ASRProvider:
        if provider_id == "faster_whisper":
            return FasterWhisperASRProvider(**kwargs)
        raise ValueError(f"Unknown ASR provider config: {provider_id}")

    @staticmethod
    def get_reasoning(provider_id: str, model_name: str, **kwargs) -> ReasoningProvider:
        if provider_id == "ollama":
            return OllamaReasoningProvider(model_name=model_name, **kwargs)
        raise ValueError(f"Unknown Reasoning provider config: {provider_id}")

    @staticmethod
    def get_tts(
        provider_id: str, voice_name: str = "af_sarah", **kwargs
    ) -> TTSProvider:
        if provider_id == "kokoro":
            return KokoroTTSProvider(voice_name=voice_name, **kwargs)
        raise ValueError(f"Unknown TTS provider config: {provider_id}")
