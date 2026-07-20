import time
from typing import List, Dict, Any
from .metrics import SessionMetrics


class ConversationSession:
    """
    Manages the state, audio buffers, history, and latencies for a single active conversation session.
    """

    def __init__(self, session_id: str):
        self.session_id: str = session_id
        self.created_at: float = time.time()
        self.last_activity: float = time.time()

        # Audio buffer for accumulating mic input bytes
        self.speech_buffer: bytearray = bytearray()

        # Transcript & turn history for the active conversation
        self.transcript: str = ""
        self.conversation_history: List[Dict[str, Any]] = []

        # Session states
        self.speaking: bool = False
        self.interrupted: bool = False

        # Latency metrics
        self.model_latency: float = 0.0
        self.metrics: SessionMetrics = SessionMetrics()

    def append_audio(self, pcm_bytes: bytes):
        """Accumulates incoming PCM audio bytes and updates last activity."""
        self.speech_buffer.extend(pcm_bytes)
        self.last_activity = time.time()

    def consume_speech_buffer(self) -> bytes:
        """Consumes and returns the accumulated speech buffer, resetting it."""
        data = bytes(self.speech_buffer)
        self.speech_buffer.clear()
        return data

    def clear_speech_buffer(self):
        """Clears the speech buffer."""
        self.speech_buffer.clear()

    def start_turn(self):
        """Prepares session states and resets latency metrics for a new turn."""
        self.speaking = True
        self.interrupted = False
        self.transcript = ""
        self.metrics.start_turn()
        self.last_activity = time.time()

    def end_turn(self, final_text: str = ""):
        """Concludes timing metrics and saves the turn in conversation history."""
        self.speaking = False
        self.transcript = final_text
        self.metrics.end_turn()
        self.model_latency = self.metrics.total_latency

        if final_text:
            self.conversation_history.append(
                {"role": "model", "text": final_text, "timestamp": time.time()}
            )
        self.last_activity = time.time()

    def append_user_turn(self, text: str):
        """Appends a user text message to history."""
        self.conversation_history.append(
            {"role": "user", "text": text, "timestamp": time.time()}
        )
        self.last_activity = time.time()
