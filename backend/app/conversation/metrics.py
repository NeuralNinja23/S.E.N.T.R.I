import time
from dataclasses import dataclass

@dataclass
class SessionMetrics:
    """
    Maintains latency, duration, and throughput metrics for tracking model performance.
    """
    turn_start_time: float = 0.0
    first_token_time: float = 0.0
    first_audio_time: float = 0.0
    turn_end_time: float = 0.0
    
    total_latency: float = 0.0
    ttft: float = 0.0  # Time to First Token (seconds)
    ttfa: float = 0.0  # Time to First Audio (seconds)
    
    audio_duration_sec: float = 0.0
    gpu_inference_time_sec: float = 0.0
    tokens_generated: int = 0
    tokens_per_second: float = 0.0

    def start_turn(self):
        """Starts timing the current user query turn."""
        self.turn_start_time = time.time()
        self.first_token_time = 0.0
        self.first_audio_time = 0.0
        self.turn_end_time = 0.0
        self.total_latency = 0.0
        self.ttft = 0.0
        self.ttfa = 0.0
        self.audio_duration_sec = 0.0
        self.gpu_inference_time_sec = 0.0
        self.tokens_generated = 0
        self.tokens_per_second = 0.0

    def record_first_token(self):
        """Records Time to First Token (TTFT)."""
        if self.first_token_time == 0.0 and self.turn_start_time > 0.0:
            self.first_token_time = time.time()
            self.ttft = self.first_token_time - self.turn_start_time

    def record_first_audio(self):
        """Records Time to First Audio (TTFA)."""
        if self.first_audio_time == 0.0 and self.turn_start_time > 0.0:
            self.first_audio_time = time.time()
            self.ttfa = self.first_audio_time - self.turn_start_time

    def add_tokens(self, count: int):
        """Accumulates token counts."""
        self.tokens_generated += count

    def end_turn(self):
        """Concludes the timing and calculates latency averages."""
        if self.turn_start_time > 0.0:
            self.turn_end_time = time.time()
            self.total_latency = self.turn_end_time - self.turn_start_time
            
            # Calculate token generation speed
            active_gen_time = self.turn_end_time - (self.first_token_time or self.turn_start_time)
            if active_gen_time > 0.001 and self.tokens_generated > 0:
                self.tokens_per_second = self.tokens_generated / active_gen_time
