from .interfaces import ISpeechToSpeechModel
from .session import ConversationSession
from .registry import InferenceRegistry, InferenceInfo
from .engine import ConversationEngine
from .miniomni import MiniOmni2Model
from .transport import ISpeechTransport, HttpSpeechTransport

# Register MiniOmni2 in InferenceRegistry upon package load
InferenceRegistry.register(
    id="miniomni2",
    version="2.0",
    modality="speech",
    implementation=MiniOmni2Model,
    runtime="http",
    capabilities={
        "speech_input",
        "speech_output",
        "streaming",
        "interruptible",
        "tool_calling",
        "vision"
    }
)

__all__ = [
    "ConversationEngine",
    "ConversationSession",
    "InferenceRegistry",
    "InferenceInfo",
    "ISpeechToSpeechModel",
    "ISpeechTransport",
    "HttpSpeechTransport"
]
