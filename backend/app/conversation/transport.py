import abc
import httpx
from typing import AsyncGenerator, Tuple, Union, Dict, Any
from app.services.logger import get_logger

logger = get_logger("speech_transport")

class ISpeechTransport(abc.ABC):
    """
    Abstract protocol defining transport contracts for conversational engines.
    """
    
    @abc.abstractmethod
    async def send_audio_request(
        self,
        url: str,
        payload: Dict[str, Any]
    ) -> AsyncGenerator[Tuple[str, Union[bytes, str]], None]:
        """Sends an audio request to the model runtime and yields (event_type, content) tuples."""
        pass

class HttpSpeechTransport(ISpeechTransport):
    """
    HTTP streaming transport parsing boundary multipart streams.
    """
    
    async def send_audio_request(
        self,
        url: str,
        payload: Dict[str, Any]
    ) -> AsyncGenerator[Tuple[str, Union[bytes, str]], None]:
        boundary = b"--frame"
        buffer = bytearray()
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        logger.error(f"HTTP Transport: server returned code {response.status_code}")
                        return
                        
                    async for chunk in response.aiter_bytes():
                        buffer.extend(chunk)
                        
                        while True:
                            first_idx = buffer.find(boundary)
                            if first_idx == -1:
                                break
                                
                            second_idx = buffer.find(boundary, first_idx + len(boundary))
                            if second_idx == -1:
                                break
                                
                            frame = buffer[first_idx + len(boundary) : second_idx]
                            del buffer[:second_idx]
                            
                            header_end = frame.find(b"\r\n\r\n")
                            if header_end == -1:
                                continue
                                
                            headers_part = frame[:header_end]
                            body_part = frame[header_end + 4:]
                            
                            if body_part.endswith(b"\r\n"):
                                body_part = body_part[:-2]
                                
                            if b"audio/wav" in headers_part:
                                yield ("audio", bytes(body_part))
                            elif b"text/plain" in headers_part:
                                yield ("text", body_part.decode("utf-8", errors="ignore"))
        except Exception as e:
            logger.error(f"HTTP Transport: stream request failed: {e}")
            yield ("error", str(e))
