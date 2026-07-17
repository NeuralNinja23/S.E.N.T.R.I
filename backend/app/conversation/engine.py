from typing import AsyncGenerator, Dict, Any
from .interfaces import ISpeechToSpeechModel
from .registry import InferenceRegistry
from .adapter import ConversationAdapter
from app.config import CONVERSATION_ENGINE

class ConversationEngine:
    """
    Core conversation engine for Sentri V2.
    Routes real-time streaming audio and text turns.
    """
    
    def __init__(self, model_id: str = None, model: ISpeechToSpeechModel = None):
        self.model_id = model_id or CONVERSATION_ENGINE
        self.model = model or InferenceRegistry.get_model(self.model_id)
        self.model_info = InferenceRegistry.get_info(self.model_id)
        
    def supports(self, capability: str) -> bool:
        """Helper to query if the active model supports a specific capability."""
        if self.model_info:
            return self.model_info.supports(capability)
        return False
        
    async def run_voice_turn(
        self, 
        input_audio_stream: AsyncGenerator[bytes, None],
        history: list = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Executes a real-time duplex voice turn.
        Yields structured statuses or audio/text/transcript packets.
        """
        if not self.model:
            yield {
                "type": "system",
                "status": "conversation_engine_missing",
                "message": "Conversation engine has not been integrated."
            }
            return
            
        if hasattr(self.model, "process_audio_stream_with_text"):
            import inspect
            sig = inspect.signature(self.model.process_audio_stream_with_text)
            if "history" in sig.parameters:
                response_gen = self.model.process_audio_stream_with_text(input_audio_stream, history=history)
            else:
                response_gen = self.model.process_audio_stream_with_text(input_audio_stream)

            async for event_type, content in response_gen:
                if event_type == "audio":
                    yield {"type": "audio", "data": content}
                elif event_type == "text":
                    yield {"type": "text", "data": content}
                elif event_type == "user_transcript":
                    yield {"type": "user_transcript", "data": content}
        else:
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
