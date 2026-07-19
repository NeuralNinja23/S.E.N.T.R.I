import logging
import re
import json
import httpx
import requests
import asyncio
import functools
from app.config import REASONING_MODEL
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
        from app.conversation.utils import ResponseCleaner
        return ResponseCleaner.clean(raw)
    
    @staticmethod
    def generate(
        system_prompt: str,
        user_content: str,
        temperature: float = 0.7,
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
                    {"role": "user", "content": user_content}
                ],
                "stream": False,
                "think": False,       # Disable thinking unconditionally
                "keep_alive": -1,
                "options": {
                    "temperature": temperature,
                    "num_ctx": 12288,
                    "repeat_penalty": 1.1
                }
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
    async def generate_async(
        system_prompt: str,
        user_content: str,
        history: list = None,          # Bug #3: accept prior conversation turns
        temperature: float = 0.7,
        stream: bool = False,
        on_token=None,
        timeout_sec: float = 120.0,
        websocket=None
    ) -> str:
        try:
            url = "http://127.0.0.1:11434/api/chat"
            
            # Bug #3: Build messages with full conversation history for multi-turn context
            messages = [{"role": "system", "content": system_prompt}]
            if history:
                for entry in history:
                    role = entry.get("role", "user")
                    content = entry.get("text") or entry.get("content", "")
                    if content:
                        messages.append({"role": role, "content": content})
            messages.append({"role": "user", "content": user_content})
            
            # Loop for multi-turn tool calling (up to 5 turns)
            for turn in range(5):
                payload = {
                    "model": REASONING_MODEL,
                    "messages": messages,
                    "stream": False,
                    "think": False,  # Disable thinking unconditionally to prevent loops
                    "keep_alive": -1,
                    "tools": TOOL_SCHEMAS,  # Pass our list of local tools
                    "options": {
                        "temperature": temperature,
                        "num_ctx": 12288,
                        "num_predict": 1024,  # Prevent runaway loops
                        "repeat_penalty": 1.1
                    }
                }
                
                async with httpx.AsyncClient(timeout=timeout_sec) as client:
                    res = await client.post(url, json=payload)
                    if res.status_code != 200:
                        logger.error(f"Ollama returned HTTP error code {res.status_code}")
                        return "Error: Failed to connect to reasoning provider."
                        
                    data = res.json()
                    message = data.get("message", {})
                    tool_calls = message.get("tool_calls", [])
                    
                    # Bug #18: Removed blocking synchronous debug file write (full_ollama_json.json)
                    if tool_calls:
                        # Append assistant message containing the tool calls to conversation history
                        messages.append(message)
                        
                        for tool_call in tool_calls:
                            func_info = tool_call.get("function", {})
                            name = func_info.get("name")
                            args = func_info.get("arguments", {})
                            
                            args_str = ", ".join([f"{k}={json.dumps(v)}" for k, v in args.items()])
                            logger.info(f"Ollama requested tool: {name}({args_str})")
                            
                            if websocket:
                                try:
                                    await websocket.send_json({
                                        "type": "system",
                                        "message": f"TOOL_CALL: {name} ({args_str})"
                                    })
                                except Exception as ws_err:
                                    logger.warning(f"Could not send TOOL_CALL log: {ws_err}")
                                    
                            # Execute the tool from TOOL_REGISTRY
                            func = TOOL_REGISTRY.get(name)
                            if func:
                                try:
                                    # Since tools are synchronous blocking I/O, execute in thread pool
                                    loop = asyncio.get_running_loop()
                                    # Partially apply the arguments
                                    pfunc = functools.partial(func, **args)
                                    result = await loop.run_in_executor(None, pfunc)
                                except Exception as exec_err:
                                    result = json.dumps({"error": f"Tool execution failed: {exec_err}"})
                            else:
                                result = json.dumps({"error": f"Tool '{name}' not found in registry."})
                                
                            logger.info(f"Tool {name} result: {str(result)[:200]}")
                            
                            if websocket:
                                try:
                                    res_summary = str(result)[:150] + ("..." if len(str(result)) > 150 else "")
                                    await websocket.send_json({
                                        "type": "system",
                                        "message": f"TOOL_RESULT: {name} -> {res_summary}"
                                    })
                                except Exception as ws_err:
                                    logger.warning(f"Could not send TOOL_RESULT log: {ws_err}")
                                    
                            # Append the tool result back to the message history
                            messages.append({
                                "role": "tool",
                                "content": str(result)
                            })
                            
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
