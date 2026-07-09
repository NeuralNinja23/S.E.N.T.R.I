import logging

logger = logging.getLogger("conversation_adapter")

class ConversationAdapter:
    """
    Adapter bridging text queries. Currently disabled as Ollama is removed.
    """
    
    @staticmethod
    def generate(
        system_prompt: str,
        user_content: str,
        temperature: float = 0.0,
        stream: bool = False,
        on_token=None,
        timeout_sec: float = None
    ) -> str:
        logger.info("Text generation requested, but Ollama model is disabled.")
        return "Ollama local model is disabled. Text-only conversations are not available."

    @staticmethod
    async def generate_async(
        system_prompt: str,
        user_content: str,
        temperature: float = 0.0,
        stream: bool = False,
        on_token=None,
        timeout_sec: float = None
    ) -> str:
        logger.info("Async text generation requested, but Ollama model is disabled.")
        return "Ollama local model is disabled. Text-only conversations are not available."

def call_llm_direct(*args, **kwargs) -> str:
    logger.info("Direct LLM call requested, but Ollama is disabled.")
    return None

def call_llm_streaming(*args, **kwargs) -> str:
    logger.info("Streaming LLM call requested, but Ollama is disabled.")
    return None
