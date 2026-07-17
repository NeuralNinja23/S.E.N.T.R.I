import logging
import httpx
import requests
from app.config import REASONING_MODEL

logger = logging.getLogger("conversation_adapter")

class ConversationAdapter:
    """
    Adapter bridging text queries using the local Ollama reasoning model.
    """
    
    @staticmethod
    def generate(
        system_prompt: str,
        user_content: str,
        temperature: float = 0.6,
        stream: bool = False,
        on_token=None,
        timeout_sec: float = 120.0
    ) -> str:
        try:
            url = "http://127.0.0.1:11434/api/chat"
            payload = {
                "model": REASONING_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content + " /no_think"}
                ],
                "stream": False,
                "keep_alive": -1,
                "options": {
                    "temperature": temperature,
                    "num_ctx": 4096
                }
            }
            res = requests.post(url, json=payload, timeout=timeout_sec)
            if res.status_code == 200:
                data = res.json()
                return data["message"]["content"]
            else:
                logger.error(f"Ollama returned HTTP error code {res.status_code}")
                return "Error: Failed to connect to reasoning provider."
        except Exception as e:
            logger.error(f"Failed to generate text response: {e}")
            return "Error: Failed to run reasoning."

    @staticmethod
    async def generate_async(
        system_prompt: str,
        user_content: str,
        temperature: float = 0.6,
        stream: bool = False,
        on_token=None,
        timeout_sec: float = 120.0
    ) -> str:
        try:
            url = "http://127.0.0.1:11434/api/chat"
            payload = {
                "model": REASONING_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content + " /no_think"}
                ],
                "stream": False,
                "keep_alive": -1,
                "options": {
                    "temperature": temperature,
                    "num_ctx": 4096
                }
            }
            async with httpx.AsyncClient(timeout=timeout_sec) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    return data["message"]["content"]
                else:
                    logger.error(f"Ollama returned HTTP error code {res.status_code}")
                    return "Error: Failed to connect to reasoning provider."
        except Exception as e:
            logger.error(f"Failed to generate async text response: {e}")
            return "Error: Failed to run reasoning."

def call_llm_direct(*args, **kwargs) -> str:
    # Direct LLM call wrapper
    system_prompt = kwargs.get("system_prompt", "") or (args[0] if len(args) > 0 else "")
    user_content = kwargs.get("user_content", "") or (args[1] if len(args) > 1 else "")
    return ConversationAdapter.generate(system_prompt, user_content)

def call_llm_streaming(*args, **kwargs) -> str:
    # Fallback wrapper
    system_prompt = kwargs.get("system_prompt", "") or (args[0] if len(args) > 0 else "")
    user_content = kwargs.get("user_content", "") or (args[1] if len(args) > 1 else "")
    return ConversationAdapter.generate(system_prompt, user_content)
