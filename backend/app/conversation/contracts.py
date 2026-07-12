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

import asyncio

@dataclass
class ConversationClock:
    """Tracks raw event timestamps and queue wait times for detailed execution profiling."""
    mic_open_time: float = 0.0
    speech_start_time: float = 0.0
    speech_end_time: float = 0.0  # VAD silence completion
    
    asr_queued_time: float = 0.0
    asr_start_time: float = 0.0
    asr_end_time: float = 0.0
    
    prompt_built_time: float = 0.0
    
    llm_queued_time: float = 0.0
    llm_start_time: float = 0.0
    first_token_time: float = 0.0
    llm_end_time: float = 0.0
    
    planner_queued_time: float = 0.0
    first_phrase_time: float = 0.0
    
    tts_queued_time: float = 0.0
    tts_start_time: float = 0.0
    first_audio_frame_time: float = 0.0
    tts_end_time: float = 0.0
    
    playback_queued_time: float = 0.0
    playback_start_time: float = 0.0
    playback_finish_time: float = 0.0

@dataclass
class TurnContext:
    """Represents the pure domain state of a conversation turn (what the system knows)."""
    turn_id: str
    cancel_token: asyncio.Event = field(default_factory=asyncio.Event)
    
    # Inputs & intermediate results
    user_audio: bytes = b""
    transcript: str = ""
    memory_context: str = ""
    system_prompt: str = ""
    reasoning_response: str = ""
    
    # Execution metrics and clock
    clock: ConversationClock = field(default_factory=ConversationClock)

class TurnChannels:
    """Represents the transport plane for streaming data between pipeline workers."""
    def __init__(self):
        self.token_queue: asyncio.Queue[str] = asyncio.Queue()
        self.phrase_queue: asyncio.Queue[str] = asyncio.Queue()
        self.audio_queue: asyncio.Queue[bytes] = asyncio.Queue()

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

