from dataclasses import dataclass, field
from typing import Dict, Any, Optional

@dataclass
class ConversationEvent:
    """Base class for all reactive conversation events."""
    timestamp: float = field(default_factory=lambda: __import__("time").time(), init=False)

@dataclass
class SpeechStarted(ConversationEvent):
    """User started speaking."""
    pass

@dataclass
class SpeechEnded(ConversationEvent):
    """User finished speaking."""
    pass

@dataclass
class TranscriptReceived(ConversationEvent):
    """Received a text transcript chunk from the model."""
    text: str

@dataclass
class ModelThinking(ConversationEvent):
    """Model is processing query or generating turn response."""
    pass

@dataclass
class AudioChunkGenerated(ConversationEvent):
    """Synthesized voice audio output chunk ready for playback."""
    audio_chunk: bytes

@dataclass
class ToolRequested(ConversationEvent):
    """Model requested a tool invocation."""
    tool_name: str
    arguments: Dict[str, Any]

@dataclass
class ToolFinished(ConversationEvent):
    """Tool invocation completed."""
    tool_name: str
    result: str

@dataclass
class ConversationFinished(ConversationEvent):
    """Response generation complete, engine ready for next turn."""
    pass

@dataclass
class ConversationInterrupted(ConversationEvent):
    """Model output generation was interrupted (e.g. user barge-in)."""
    reason: str = "user_interrupt"

@dataclass
class ConversationError(ConversationEvent):
    """An error occurred during turn processing."""
    error_message: str
    error_type: Optional[str] = None
