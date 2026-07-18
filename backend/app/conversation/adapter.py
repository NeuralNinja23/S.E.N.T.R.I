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
        """Strip <think>...</think> blocks, normalize whitespace, and strip generic assistant clichés."""
        if not raw:
            return ""
        cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
        
        # 1. Clean out the "I don't have that information" prefix for casual queries (jokes/stories/tools)
        cleaned = re.sub(r"^[iI] don't have that information\.\s*(If you'd like to hear another type of story or need assistance with something else, feel free to let me know!)?\s*", "", cleaned)
        cleaned = re.sub(r"^[iI] don't have that information\.\s*(If you'd like, I can remember it for next time we chat!)?\s*", "", cleaned)
        cleaned = re.sub(r"^[iI] don't have that information\.\s*(I'm Sentri, here to assist with any questions or tasks within my capabilities!?)?\s*", "", cleaned)
        cleaned = re.sub(r"^[iI] don't have that information\.\s*", "", cleaned)
        
        # 2. Strip generic customer support clichés programmatically ONLY at the very end of the string.
        # Uses loose matching to catch variants (e.g. "this fine day", "further today", "resources", "instruments").
        cliches = [
            r"\b[hH]ow (can|may) I (further |help |assist |serve ).*\??\s*$",
            r"\b[iI]s there anything else (you would prefer to discuss|I can help|I can assist|you'd like|you would prefer).*\??\s*$",
            r"\b[wW]hat else can I (do|help).*\??\s*$",
            r"\b[hH]ow may these .* serve us today\??\s*$",
            r"\b[iI]'m Sentri, (here to assist|here to help).*\s*$"
        ]
        for cliche in cliches:
            cleaned = re.sub(cliche, "", cleaned, flags=re.IGNORECASE)
            
        return cleaned.strip()
    
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
        temperature: float = 0.7,
        stream: bool = False,
        on_token=None,
        timeout_sec: float = 120.0,
        websocket=None
    ) -> str:
        try:
            url = "http://127.0.0.1:11434/api/chat"
            
            # Build conversation context messages history
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ]
            
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
                    
                    # Log the JSON for debugging
                    try:
                        json_path = r"C:\Users\JARVIS\.gemini\antigravity-ide\brain\05416677-6b3f-44a9-ab02-29fddfedefe5\scratch\full_ollama_json.json"
                        with open(json_path, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2, ensure_ascii=False)
                    except Exception as json_err:
                        logger.error(f"Failed to write full json log: {json_err}")
                    
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
                        try:
                            raw_path = r"C:\Users\JARVIS\.gemini\antigravity-ide\brain\05416677-6b3f-44a9-ab02-29fddfedefe5\scratch\raw_ollama_response.txt"
                            with open(raw_path, "w", encoding="utf-8") as f:
                                f.write(raw_content)
                        except Exception as raw_err:
                            logger.error(f"Failed to write raw response log: {raw_err}")
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
