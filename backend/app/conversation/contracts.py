import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class ComponentMetrics:
    """Latency metrics for a single component in the pipeline."""
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0

    def start(self):
        self.start_time = time.time()

    def stop(self):
        if self.start_time > 0.0:
            self.end_time = time.time()
            self.duration = self.end_time - self.start_time

@dataclass
class VoiceMetrics:
    """Hierarchical metrics for a conversation turn."""
    asr: ComponentMetrics = field(default_factory=ComponentMetrics)
    llm: ComponentMetrics = field(default_factory=ComponentMetrics)
    chunker: ComponentMetrics = field(default_factory=ComponentMetrics)
    tts: ComponentMetrics = field(default_factory=ComponentMetrics)
    end_to_end: ComponentMetrics = field(default_factory=ComponentMetrics)
    
    ttft: float = 0.0  # Time to First Token
    ttfa: float = 0.0  # Time to First Audio

@dataclass
class ReasoningRequest:
    """
    Standard request payload containing system prompt, memory, history, and user input
    to be serialized by reasoning providers.
    """
    system_prompt: str
    user_input: str
    memory: Optional[str] = None
    history: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class ReasoningResponse:
    """
    Payload containing the generated text response or response token.
    """
    text: str

@dataclass
class AudioChunk:
    """
    Payload containing synthesized PCM16 binary chunks and metadata.
    """
    pcm_bytes: bytes
    sample_rate: int = 24000
    duration_ms: float = 0.0

@dataclass
class Transcript:
    """
    ASR transcribed text payload.
    """
    text: str

@dataclass
class ConversationTurn:
    """
    Unified object representing the entire interaction lifecycle of a single speech turn.
    """
    id: str
    timestamp: float = field(default_factory=time.time)
    transcript: Optional[str] = None
    memory_context: Optional[str] = None
    reasoning_request: Optional[ReasoningRequest] = None
    reasoning_response: Optional[str] = None
    audio_chunks: List[AudioChunk] = field(default_factory=list)
    metrics: VoiceMetrics = field(default_factory=VoiceMetrics)
