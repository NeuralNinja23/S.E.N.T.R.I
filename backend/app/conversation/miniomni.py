import os
import wave
import tempfile
import base64
from typing import AsyncGenerator, Tuple, Union, Dict, Any
from app.services.logger import get_logger
from app.config import MINIOMNI_SERVER, MINIOMNI_PORT
from .interfaces import ISpeechToSpeechModel
from .transport import ISpeechTransport, HttpSpeechTransport

logger = get_logger("miniomni_model")

class MiniOmni2Model(ISpeechToSpeechModel):
    """
    MiniOmni2 integration driver calling the local server daemon over SpeechTransport.
    """
    
    def __init__(self, transport: ISpeechTransport = None):
        self.transport = transport or HttpSpeechTransport()
        # Build server URL from config settings
        self.server_url = f"{MINIOMNI_SERVER}:{MINIOMNI_PORT}/chat"

    async def process_audio_stream_with_text(
        self,
        audio_generator: AsyncGenerator[bytes, None]
    ) -> AsyncGenerator[Tuple[str, Union[bytes, str]], None]:
        """
        Processes incoming real-time audio bytes and yields both 
        sound chunks and text transcripts as they arrive.
        """
        # 1. Accumulate audio bytes
        audio_data = bytearray()
        async for chunk in audio_generator:
            audio_data.extend(chunk)
            
        if not audio_data:
            logger.warning("MiniOmni2: Received empty speech stream.")
            return

        # 2. Write to a temp WAV file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
            temp_wav_path = temp_wav.name
            
        try:
            with wave.open(temp_wav_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)  # Input PCM is 16kHz
                wf.writeframes(audio_data)
        except Exception as e:
            logger.error(f"MiniOmni2: Failed to write temp wav input: {e}")
            return
            
        # 3. Read and encode to base64
        try:
            with open(temp_wav_path, "rb") as f:
                encoded_audio = base64.b64encode(f.read()).decode("utf-8")
        finally:
            try:
                os.remove(temp_wav_path)
            except Exception:
                pass
                
        # 4. Stream POST request via Transport layer
        payload = {
            "audio": encoded_audio,
            "stream_stride": 4,
            "max_tokens": 2048
        }
        
        async for event_type, content in self.transport.send_audio_request(self.server_url, payload):
            yield event_type, content

    async def process_audio_stream(
        self,
        audio_generator: AsyncGenerator[bytes, None]
    ) -> AsyncGenerator[bytes, None]:
        """Complies with standard ISpeechToSpeechModel interface yielding audio bytes only."""
        async for event_type, content in self.process_audio_stream_with_text(audio_generator):
            if event_type == "audio":
                yield content
