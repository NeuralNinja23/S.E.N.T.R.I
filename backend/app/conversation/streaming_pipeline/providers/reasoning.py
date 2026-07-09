import json
import httpx
import logging
from abc import ABC, abstractmethod
from typing import AsyncGenerator
from app.conversation.contracts import ReasoningRequest

logger = logging.getLogger("reasoning_provider")

class ReasoningProvider(ABC):
    """
    Interface for LLM reasoning providers.
    """
    @abstractmethod
    async def stream(self, request: ReasoningRequest) -> AsyncGenerator[str, None]:
        """
        Streams response text tokens given a unified ReasoningRequest payload.
        """
        pass

class OllamaReasoningProvider(ReasoningProvider):
    """
    Reasoning provider using local Ollama HTTP endpoints.

    Uses a single persistent httpx.AsyncClient (created once at init, reused
    for every request) to avoid TCP connection setup/teardown overhead per turn.
    """
    def __init__(self, model_name: str, base_url: str = "http://127.0.0.1:11434"):
        self.model_name = model_name
        self.base_url = base_url
        # Single persistent client — avoids creating/tearing down TCP connections per turn
        self._client = httpx.AsyncClient(timeout=120.0)

    async def stream(self, request: ReasoningRequest) -> AsyncGenerator[str, None]:
        system_content = request.system_prompt
        if request.memory and request.memory.strip():
            system_content += f"\n\n[GRAPH MEMORY STORE]\n{request.memory}\n"

        # Map history messages to Ollama chat protocol formats
        mapped_history = []
        for msg in request.history:
            role = msg.get("role")
            if role == "model":
                role = "assistant"
            mapped_history.append({
                "role": role,
                "content": msg.get("text", "")
            })

        messages = [{"role": "system", "content": system_content}]
        messages.extend(mapped_history)
        # Append /no_think to disable Qwen3.x thinking mode for real-time voice.
        # Thinking mode spends 30-60s on internal reasoning before the first token,
        # which is completely incompatible with low-latency voice responses.
        user_content = request.user_input.strip() + " /no_think"
        messages.append({"role": "user", "content": user_content})

        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
            "keep_alive": -1,       # Never evict from VRAM between turns
            "think": False,         # Disable thinking mode (Qwen3.x / Ollama >=0.6)
            "options": {
                "temperature": 0.6,
                "num_ctx": 4096     # Reduced KV cache: 16384->4096 saves ~1.5GB VRAM
            }
        }

        try:
            async with self._client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    logger.error(f"Ollama endpoint returned HTTP error {response.status_code}")
                    return

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)

                        # Stream tokens to caller
                        token = data.get("message", {}).get("content", "")
                        if token:
                            yield token

                        # Final chunk contains Ollama's internal timing breakdown
                        if data.get("done"):
                            load_ms   = data.get("load_duration", 0) / 1e6
                            prompt_ms = data.get("prompt_eval_duration", 0) / 1e6
                            eval_ms   = data.get("eval_duration", 0) / 1e6
                            total_ms  = data.get("total_duration", 0) / 1e6
                            eval_count = data.get("eval_count", 0)
                            tok_per_s  = (eval_count / (eval_ms / 1000)) if eval_ms > 0 else 0

                            logger.info(
                                f"[OLLAMA TIMING] "
                                f"load={load_ms:.0f}ms | "
                                f"prompt_eval={prompt_ms:.0f}ms | "
                                f"eval={eval_ms:.0f}ms ({eval_count} tokens, {tok_per_s:.1f} tok/s) | "
                                f"total={total_ms:.0f}ms"
                            )

                            if load_ms > 500:
                                logger.warning(
                                    f"[OLLAMA] High load_duration ({load_ms:.0f}ms) — "
                                    "model was not resident in VRAM. Check keep_alive and VRAM pressure."
                                )

                    except Exception as parse_err:
                        logger.error(f"Failed to parse Ollama JSON chunk: {parse_err}")

        except Exception as conn_err:
            logger.error(f"Ollama stream HTTP request failed: {conn_err}")
