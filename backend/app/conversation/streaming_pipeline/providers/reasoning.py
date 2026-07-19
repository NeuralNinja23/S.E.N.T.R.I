import json
import httpx
import logging
import asyncio
import functools
from abc import ABC, abstractmethod
from typing import AsyncGenerator
from app.conversation.contracts import ReasoningRequest

logger = logging.getLogger("reasoning_provider")

class ReasoningProvider(ABC):
    """
    Interface for LLM reasoning providers.
    """
    @abstractmethod
    async def stream(self, request: ReasoningRequest, websocket=None) -> AsyncGenerator[str, None]:
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

    async def stream(self, request: ReasoningRequest, websocket=None) -> AsyncGenerator[str, None]:
        # Import tools and registry dynamically to prevent circular imports
        from app.tasks.tool_schemas import TOOL_SCHEMAS
        from app.tasks.task_registry import TOOL_REGISTRY

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
                "content": msg.get("text", "") or msg.get("content", "")
            })

        messages = [{"role": "system", "content": system_content}]
        messages.extend(mapped_history)
        
        # Append /no_think to disable Qwen3.x thinking mode for real-time voice.
        user_content = request.user_input.strip() + " /no_think"
        messages.append({"role": "user", "content": user_content})

        url = f"{self.base_url}/api/chat"

        # Loop up to 5 turns for tool calling
        for turn in range(5):
            payload = {
                "model": self.model_name,
                "messages": messages,
                "stream": True,         # Bug #4: Enable true streaming
                "think": False,         # Disable thinking mode
                "keep_alive": -1,       # Keep model in VRAM
                "tools": TOOL_SCHEMAS,  # Pass tools list
                "options": {
                    "temperature": 0.6,
                    "num_ctx": 12288,
                    "num_predict": 1024,  # Bug #6: cap tokens to prevent runaway voice generation
                    "repeat_penalty": 1.1
                }
            }

            try:
                async with self._client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        logger.error(f"Ollama endpoint returned HTTP error {response.status_code}")
                        return

                    tool_calls = []
                    assistant_message = {"role": "assistant", "content": ""}
                    
                    class ThinkTagStripper:
                        def __init__(self):
                            self.buffer = ""
                            self.in_think = False

                        def feed(self, token: str) -> str:
                            self.buffer += token
                            if "<think>" in self.buffer and not self.in_think:
                                parts = self.buffer.split("<think>", 1)
                                before = parts[0]
                                self.buffer = parts[1]
                                self.in_think = True
                                return before
                            if self.in_think:
                                if "</think>" in self.buffer:
                                    parts = self.buffer.split("</think>", 1)
                                    self.buffer = parts[1]
                                    self.in_think = False
                                    return self.feed("")
                                else:
                                    self.buffer = ""
                                    return ""
                            else:
                                if any(self.buffer.endswith(self.buffer[:i]) for i in range(1, len(self.buffer)) if "<think>".startswith(self.buffer[:i])):
                                    return ""
                                out = self.buffer
                                self.buffer = ""
                                return out

                    stripper = ThinkTagStripper()

                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        chunk = json.loads(line)
                        msg_chunk = chunk.get("message", {})
                        
                        # Accumulate tool calls if present in the stream
                        chunk_tool_calls = msg_chunk.get("tool_calls", [])
                        for tc in chunk_tool_calls:
                            idx = tc.get("index", 0)
                            while len(tool_calls) <= idx:
                                tool_calls.append({
                                    "id": "",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""}
                                })
                            target = tool_calls[idx]
                            if tc.get("id"):
                                target["id"] = tc["id"]
                            if tc.get("type"):
                                target["type"] = tc["type"]
                            
                            tc_func = tc.get("function", {})
                            if tc_func.get("name"):
                                target["function"]["name"] = tc_func["name"]
                            
                            tc_args = tc_func.get("arguments", "")
                            if tc_args:
                                if isinstance(tc_args, dict):
                                    if not isinstance(target["function"]["arguments"], dict):
                                        target["function"]["arguments"] = {}
                                    target["function"]["arguments"].update(tc_args)
                                else:
                                    if isinstance(target["function"]["arguments"], dict):
                                        target["function"]["arguments"] = ""
                                    target["function"]["arguments"] += tc_args

                        # Stream content if present
                        content_chunk = msg_chunk.get("content", "")
                        if content_chunk:
                            # Strip /no_think suffix if echoes back
                            content_chunk = content_chunk.replace("/no_think", "")
                            cleaned_token = stripper.feed(content_chunk)
                            if cleaned_token:
                                assistant_message["content"] += cleaned_token
                                yield cleaned_token

                    # Post-process tool calls arguments if they are strings
                    for tc in tool_calls:
                        func_info = tc.get("function", {})
                        args = func_info.get("arguments", "")
                        if isinstance(args, str) and args.strip():
                            try:
                                func_info["arguments"] = json.loads(args)
                            except Exception as parse_err:
                                logger.error(f"Failed to parse streamed tool call arguments JSON: {parse_err}")
                                func_info["arguments"] = {}

                if tool_calls:
                    # Append assistant message containing the tool calls to conversation history
                    assistant_message["tool_calls"] = tool_calls
                    messages.append(assistant_message)

                    for tool_call in tool_calls:
                        func_info = tool_call.get("function", {})
                        name = func_info.get("name")
                        args = func_info.get("arguments", {})

                        args_str = ", ".join([f"{k}={json.dumps(v)}" for k, v in args.items()])
                        logger.info(f"[VOICE TURN] Ollama requested tool: {name}({args_str})")

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
                                loop = asyncio.get_running_loop()
                                pfunc = functools.partial(func, **args)
                                result = await loop.run_in_executor(None, pfunc)
                            except Exception as exec_err:
                                result = json.dumps({"error": f"Tool execution failed: {exec_err}"})
                        else:
                            result = json.dumps({"error": f"Tool '{name}' not found in registry."})

                        logger.info(f"[VOICE TURN] Tool {name} result: {str(result)[:200]}")

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

                    # Continue to next turn to let Ollama reason on the tool results
                    continue

                else:
                    # No tool calls requested, text turn finished streaming
                    return

            except Exception as e:
                logger.error(f"Error in Ollama tool calling loop: {e}")
                return
