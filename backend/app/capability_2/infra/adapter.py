import logging
import json
import httpx
import requests
import asyncio
import functools
from app.config import REASONING_MODEL, OLLAMA_NUM_CTX
from app.tasks.tool_schemas import TOOL_SCHEMAS
from app.tasks.task_registry import TOOL_REGISTRY

logger = logging.getLogger("conversation_adapter")


class ConversationAdapter:
    """
    Adapter bridging text queries using the local Ollama reasoning model.
    """

    @staticmethod
    def _clean_response(raw: str) -> str:
        """Strip <think>...</think> blocks, normalize whitespace, and strip generic assistant clichés using shared ResponseCleaner."""
        from app.capability_2.infra.utils import ResponseCleaner

        return ResponseCleaner.clean(raw)

    @staticmethod
    def generate(
        system_prompt: str,
        user_content: str,
        temperature: float = 0.7,
        stream: bool = False,
        timeout_sec: float = 120.0,
    ) -> str:
        try:
            url = "http://127.0.0.1:11434/api/chat"
            payload = {
                "model": REASONING_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                "stream": False,
                "think": False,  # Disable thinking unconditionally
                "keep_alive": -1,
                "options": {
                    "temperature": temperature,
                    "num_ctx": 12288,
                    "repeat_penalty": 1.1,
                },
            }
            res = requests.post(url, json=payload, timeout=timeout_sec)
            if res.status_code == 200:
                data = res.json()
                return ConversationAdapter._clean_response(data["message"]["content"])
            else:
                logger.error(f"Ollama returned HTTP error code {res.status_code}")
                return "Error: Failed to connect to reasoning provider."
        except Exception as e:
            logger.error(f"Failed to generate text response: {e}")
            return "Error: Failed to run reasoning."

    @staticmethod
    def _should_enable_tools(user_content: str, system_prompt: str) -> bool:
        """Determines whether to send heavy tool schemas based on intent keywords or tool triggers."""
        text = user_content.lower()

        tool_keywords = [
            "search", "find", "file", "dir", "folder", "read", "write", "create", "delete",
            "run", "execute", "tool", "memory", "remember", "forget", "list", "web", "fetch",
            "url", "http", "system", "process", "task", "stats", "weather", "calculator", "calculate"
        ]
        return any(kw in text for kw in tool_keywords)

    @staticmethod
    async def generate_async(
        system_prompt: str,
        user_content: str,
        history: list | None = None,
        temperature: float = 0.7,
        stream: bool = False,
        timeout_sec: float = 120.0,
        websocket=None,
        tools: list | None = None,
    ) -> str:
        try:
            url = "http://127.0.0.1:11434/api/chat"

            messages = [{"role": "system", "content": system_prompt}]
            if history:
                for entry in history:
                    role = entry.get("role", "user")
                    content = entry.get("text") or entry.get("content", "")
                    if content:
                        messages.append({"role": role, "content": content})
            messages.append({"role": "user", "content": user_content})

            # Determine whether to attach tool schemas
            use_tools = False
            if tools is not None:
                use_tools = True
                tool_schemas_to_send = tools
            elif ConversationAdapter._should_enable_tools(user_content, system_prompt):
                use_tools = True
                tool_schemas_to_send = TOOL_SCHEMAS

            # Loop for multi-turn tool calling (up to 5 turns)
            for turn in range(5):
                payload = {
                    "model": REASONING_MODEL,
                    "messages": messages,
                    "stream": False,
                    "think": False,  # Disable thinking unconditionally to prevent loops
                    "keep_alive": -1,
                    "options": {
                        "temperature": temperature,
                        "num_ctx": OLLAMA_NUM_CTX,
                        "num_predict": 512,  # Prevent runaway loops
                        "repeat_penalty": 1.1,
                    },
                }
                if use_tools:
                    payload["tools"] = tool_schemas_to_send

                async with httpx.AsyncClient(timeout=timeout_sec) as client:
                    res = await client.post(url, json=payload)
                    if res.status_code != 200:
                        logger.error(
                            f"Ollama returned HTTP error code {res.status_code}"
                        )
                        return "Error: Failed to connect to reasoning provider."

                    data = res.json()
                    message = data.get("message", {})
                    tool_calls = message.get("tool_calls", [])


                    # Bug #18: Removed blocking synchronous debug file write (full_ollama_json.json)
                    if tool_calls:
                        # Append clean assistant message containing the tool calls to conversation history
                        clean_assistant_msg = {"role": "assistant", "content": message.get("content", "")}
                        if "tool_calls" in message:
                            clean_assistant_msg["tool_calls"] = message["tool_calls"]
                        messages.append(clean_assistant_msg)

                        for tool_call in tool_calls:
                            func_info = tool_call.get("function", {})
                            name = func_info.get("name")
                            args = func_info.get("arguments", {})
                            tc_id = tool_call.get("id")

                            args_str = ", ".join(
                                [f"{k}={json.dumps(v)}" for k, v in args.items()]
                            )
                            logger.info(f"Ollama requested tool: {name}({args_str})")

                            if websocket:
                                try:
                                    await websocket.send_json(
                                        {
                                            "type": "system",
                                            "message": f"TOOL_CALL: {name} ({args_str})",
                                        }
                                    )
                                except Exception as ws_err:
                                    logger.warning(
                                        f"Could not send TOOL_CALL log: {ws_err}"
                                    )

                            # Execute the tool from TOOL_REGISTRY
                            func = TOOL_REGISTRY.get(name)
                            if func:
                                try:
                                    # Since tools are synchronous blocking I/O, execute in thread pool
                                    loop = asyncio.get_running_loop()
                                    pfunc = functools.partial(func, **args)
                                    result = await loop.run_in_executor(None, pfunc)
                                except Exception as exec_err:
                                    result = json.dumps(
                                        {"error": f"Tool execution failed: {exec_err}"}
                                    )
                            else:
                                result = json.dumps(
                                    {"error": f"Tool '{name}' not found in registry."}
                                )

                            logger.info(f"Tool {name} result: {result[:200]}")

                            if websocket:
                                try:
                                    res_summary = result[:150] + (
                                        "..." if len(result) > 150 else ""
                                    )
                                    await websocket.send_json(
                                        {
                                            "type": "system",
                                            "message": f"TOOL_RESULT: {name} -> {res_summary}",
                                        }
                                    )
                                except Exception as ws_err:
                                    logger.warning(
                                        f"Could not send TOOL_RESULT log: {ws_err}"
                                    )

                            # Append the tool result back to the message history with tool_call_id
                            tool_msg = {"role": "tool", "name": name, "content": str(result)}
                            if tc_id:
                                tool_msg["tool_call_id"] = tc_id
                            messages.append(tool_msg)

                        # Continue to the next turn to let Ollama reason on the tool results
                        continue

                    else:
                        # No tool calls requested, this is the final text response!
                        raw_content = message.get("content", "")
                        # Bug #18: Removed blocking synchronous debug file write (raw_ollama_response.txt)
                        return ConversationAdapter._clean_response(raw_content)

            # If we completed 5 turns and still calling tools, return a warning
            return "Sentri: The query required too many nested steps to complete."
        except Exception as e:
            print(f"DEBUG EXCEPTION: {e}", flush=True)
            logger.error(f"Failed to generate async text response: {e}")
            return f"Error: {e}"



def call_llm_direct(*args, **kwargs) -> str:
    # Direct LLM call wrapper
    system_prompt = kwargs.get("system_prompt", "") or (
        args[0] if len(args) > 0 else ""
    )
    user_content = kwargs.get("user_content", "") or (args[1] if len(args) > 1 else "")
    return ConversationAdapter.generate(system_prompt, user_content)


def call_llm_streaming(*args, **kwargs) -> str:
    # Fallback wrapper
    system_prompt = kwargs.get("system_prompt", "") or (
        args[0] if len(args) > 0 else ""
    )
    user_content = kwargs.get("user_content", "") or (args[1] if len(args) > 1 else "")
    return ConversationAdapter.generate(system_prompt, user_content)
