class ConversationSession:
    """
    Tracks state and audio buffer metrics for a single live voice WebSocket connection.
    """
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.is_active = True
        self.total_frames_received = 0
        self.total_frames_sent = 0
        
    def record_input_audio(self, size_bytes: int):
        """Records metrics for incoming audio packet sizes."""
        self.total_frames_received += size_bytes
        
    def record_output_audio(self, size_bytes: int):
        """Records metrics for outgoing audio packet sizes."""
        self.total_frames_sent += size_bytes
