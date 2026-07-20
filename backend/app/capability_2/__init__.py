from .core.interfaces import ISpeechToSpeechModel
from .core.session import ConversationSession
from .core.registry import InferenceRegistry, InferenceInfo
from .core.engine import ConversationEngine
from .streaming_pipeline import StreamingSpeechPipeline

# Register the restored local Decoupled StreamingSpeechPipeline
InferenceRegistry.register(
    id="decoupled_pipeline",
    version="2.0",
    modality="speech",
    implementation=StreamingSpeechPipeline,
    runtime="local",
    capabilities={"speech_input", "speech_output", "streaming", "interruptible"},
)

__all__ = [
    "ConversationEngine",
    "ConversationSession",
    "InferenceRegistry",
    "InferenceInfo",
    "ISpeechToSpeechModel",
    "StreamingSpeechPipeline",
]
