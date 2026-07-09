import os
import wave
import tempfile
import base64
import httpx
from typing import AsyncGenerator, Tuple, Union
from app.services.logger import get_logger
from .interfaces import ISpeechToSpeechModel

logger = get_logger("miniomni_model")

async def parse_multipart_stream(response: httpx.Response) -> AsyncGenerator[Tuple[str, Union[bytes, str]], None]:
    """Parses binary multipart/x-mixed-replace stream from MiniOmni2 backend."""
    boundary = b"--frame"
    buffer = bytearray()
    
    async for chunk in response.aiter_bytes():
        buffer.extend(chunk)
        
        while True:
            # Find the first boundary marker
            first_idx = buffer.find(boundary)
            if first_idx == -1:
                break
                
            # Find the subsequent boundary marker
            second_idx = buffer.find(boundary, first_idx + len(boundary))
            if second_idx == -1:
                # Incomplete frame, wait for more chunks
                break
                
            # Extract raw frame
            frame = buffer[first_idx + len(boundary) : second_idx]
            
            # Slice processed content from buffer
            del buffer[:second_idx]
            
            # Locate end of headers marker
            header_end = frame.find(b"\r\n\r\n")
            if header_end == -1:
                continue
                
            headers_part = frame[:header_end]
            body_part = frame[header_end + 4:]
            
            # Strip trailing CRLF
            if body_part.endswith(b"\r\n"):
                body_part = body_part[:-2]
                
            # Cleanly yields components based on boundary content-types
            if b"audio/wav" in headers_part:
                yield ("audio", bytes(body_part))
            elif b"text/plain" in headers_part:
                yield ("text", body_part.decode("utf-8", errors="ignore"))

class MiniOmni2Model(ISpeechToSpeechModel):
    """
    MiniOmni2 integration driver calling the local server daemon over streaming API.
    """
    
    def __init__(self, server_url: str = "http://127.0.0.1:60808/chat"):
        self.server_url = server_url

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
                
        # 4. Stream POST to local Flask server
        payload = {
            "audio": encoded_audio,
            "stream_stride": 4,
            "max_tokens": 2048
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", self.server_url, json=payload) as response:
                    if response.status_code != 200:
                        logger.error(f"MiniOmni2 server returned error code: {response.status_code}")
                        return
                        
                    async for event_type, content in parse_multipart_stream(response):
                        yield event_type, content
        except Exception as e:
            logger.error(f"Failed to communicate with MiniOmni2 streaming server: {e}")

    async def process_audio_stream(
        self,
        audio_generator: AsyncGenerator[bytes, None]
    ) -> AsyncGenerator[bytes, None]:
        """Complies with standard ISpeechToSpeechModel interface yielding audio bytes only."""
        async for event_type, content in self.process_audio_stream_with_text(audio_generator):
            if event_type == "audio":
                yield content
