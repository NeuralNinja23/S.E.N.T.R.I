import abc
from typing import AsyncGenerator

class ISpeechToSpeechModel(abc.ABC):
    """
    Abstract interface for streaming speech-to-speech models in Sentinel V2.
    """
    
    @abc.abstractmethod
    async def process_audio_stream(
        self, 
        audio_generator: AsyncGenerator[bytes, None]
    ) -> AsyncGenerator[bytes, None]:
        """
        Accepts a stream of input audio chunks (PCM bytes) and yields a stream 
        of output audio response chunks (PCM bytes).
        """
        pass
