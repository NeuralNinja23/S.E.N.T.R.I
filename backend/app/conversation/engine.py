from typing import AsyncGenerator, Dict, Any
from .interfaces import ISpeechToSpeechModel
from .adapter import ConversationAdapter

class ConversationEngine:
    """
    Core conversation engine for Sentinel V2.
    Routes real-time streaming audio and text turns.
    """
    
    def __init__(self, model: ISpeechToSpeechModel = None):
        self.model = model
        
    async def run_voice_turn(
        self, 
        input_audio_stream: AsyncGenerator[bytes, None]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Executes a real-time duplex voice turn.
        Yields structured statuses or audio packets.
        """
        if not self.model:
            yield {
                "type": "system",
                "status": "conversation_engine_missing",
                "message": "Conversation engine has not been integrated."
            }
            return
            
        async for output_chunk in self.model.process_audio_stream(input_audio_stream):
            yield {"type": "audio", "data": output_chunk}
            
    @staticmethod
    async def run_text_turn(
        system_prompt: str,
        text_query: str
    ) -> str:
        """
        Executes a text reasoning query by routing to the adapter.
        """
        return await ConversationAdapter.generate_async(
            system_prompt=system_prompt,
            user_content=text_query
        )
