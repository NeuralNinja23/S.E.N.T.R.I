import json
import asyncio
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.config import STANDBY_TIMEOUT_SECONDS, get_system_instruction
from app.services.logger import get_logger
from app.runtime.runtime_state import runtime_store, RuntimeState, runtime_events
from app.runtime.runtime_service import runtime_service

from app.conversation import ConversationEngine, ConversationSession
from app.api.upload import get_all_documents_text_context

router = APIRouter()

async def safe_send_json(websocket: WebSocket, payload: dict):
    if websocket.client_state == WebSocketState.CONNECTED:
        try:
            await websocket.send_json(payload)
        except Exception:
            pass

async def safe_send_bytes(websocket: WebSocket, data: bytes):
    if websocket.client_state == WebSocketState.CONNECTED:
        try:
            await websocket.send_bytes(data)
        except Exception:
            pass
logger = get_logger("websocket")

conversation_engine = ConversationEngine()

from app.memory.runtime import MemoryRuntime
from app.memory.context_builder import MemoryContextBuilder
from app.memory.contracts import MemoryQuery

memory_runtime = MemoryRuntime()


async def process_user_turn(speech_bytes: bytes, websocket: WebSocket, session: ConversationSession):
    """Processes speech input with MiniOmni2, tracking TTFT and TTFA latency metrics."""
    session.start_turn()
    try:
        # Set UI state to THINKING
        await safe_send_json(websocket, {"type": "state", "state": "THINKING"})
        
        # Helper generator yielding collected speech bytes
        async def audio_generator():
            yield speech_bytes
            
        logger.info(f"[SESSION {session.session_id}] Sending speech turn to ConversationEngine...")
        response_generator = conversation_engine.run_voice_turn(
            audio_generator(),
            history=session.conversation_history
        )
        
        first_chunk = True
        accumulated_text = []
        
        async for chunk in response_generator:
            if not session.speaking:
                logger.info(f"[SESSION {session.session_id}] Speech turn aborted/interrupted by governance.")
                break

            if chunk.get("type") == "system" and chunk.get("status") == "conversation_engine_missing":
                await safe_send_json(websocket, chunk)
                break
                
            if first_chunk:
                # Set UI state back to READY for streaming reply
                await safe_send_json(websocket, {"type": "state", "state": "READY"})
                first_chunk = False
                
            if chunk["type"] == "audio":
                session.metrics.record_first_audio()
                await safe_send_bytes(websocket, chunk["data"])
                await asyncio.sleep(0.005)  # Flow control
            elif chunk["type"] == "text":
                session.metrics.record_first_token()
                session.metrics.add_tokens(len(chunk["data"].split()))
                accumulated_text.append(chunk["data"])
            elif chunk["type"] == "user_transcript":
                session.append_user_turn(chunk["data"])
                print(f"\n\n🗣️  [USER SPEAK]: {chunk['data']}\n", flush=True)
                await safe_send_json(websocket, {"type": "user", "data": chunk["data"]})
                
        final_response = "".join(accumulated_text).strip()
        # Send the complete response as a single message to the chatbox
        if final_response:
            await safe_send_json(websocket, {"type": "text", "data": final_response})
        print(f"🤖 [SENTRI SPEAK]: {final_response}\n", flush=True)
        session.end_turn(final_text=final_response)
        
        # Log latency results
        logger.info(
            f"[METRICS] Turn complete. Latency details:\n"
            f"  - TTFT (Time to First Token): {session.metrics.ttft:.3f}s\n"
            f"  - TTFA (Time to First Audio): {session.metrics.ttfa:.3f}s\n"
            f"  - Total Latency: {session.model_latency:.3f}s\n"
            f"  - Tokens generated: {session.metrics.tokens_generated} ({session.metrics.tokens_per_second:.1f} tok/sec)"
        )
                
    except Exception as e:
        logger.error(f"Error in speech processing turn: {e}")
        session.speaking = False
    finally:
        await safe_send_json(websocket, {"type": "state", "state": "READY"})

async def process_user_text_turn(text_query: str, websocket: WebSocket, session: ConversationSession):
    """Processes text query directly, returning text reply without TTS."""
    session.start_turn()
    session.append_user_turn(text_query)
    try:
        # Send USER log to frontend
        print(f"\n\n⌨️  [USER TEXT]: {text_query}\n", flush=True)
        await safe_send_json(websocket, {"type": "user", "data": text_query})
        
        # Check for memory erasure requests (e.g. "forget Rohan")
        query_lower = text_query.lower().strip()
        if any(kw in query_lower for kw in ["forget ", "forget about ", "delete ", "erase ", "remove from memory", "clear memory"]):
            target = ""
            for kw in ["forget about", "forget", "delete", "erase", "remove from memory", "clear memory"]:
                if kw in query_lower:
                    target = query_lower.split(kw)[-1].strip()
                    break
            
            import string
            target = target.strip(string.punctuation)
            if target:
                words = [w for w in target.split() if w not in ("about", "my", "the", "from", "your", "memory", "that", "record")]
                if words:
                    all_memories = memory_runtime.list_memories()
                    deleted_count = 0
                    for entry in all_memories:
                        match = False
                        for w in words:
                            if (w in entry.category.lower() or
                                w in entry.subject.lower() or 
                                w in entry.predicate.lower() or 
                                w in entry.object.lower()):
                                match = True
                                break
                        if match:
                            memory_runtime.delete(entry.id)
                            deleted_count += 1
                    
                    if deleted_count > 0:
                        response_text = "I have removed that information from this conversation. It won't be treated as part of your long-term profile unless you tell me otherwise."
                        logger.info(f"Memory erasure executed for words {words}. Deleted {deleted_count} entries.")
                    else:
                        response_text = "I have removed that pending information from this conversation. It won't be treated as part of your long-term profile unless you tell me otherwise."
                    
                    await safe_send_json(websocket, {"type": "text", "data": response_text})
                    await safe_send_json(websocket, {"type": "state", "state": "READY"})
                    session.end_turn(final_text=response_text)
                    return
        
        # Set UI state to THINKING
        await safe_send_json(websocket, {"type": "state", "state": "THINKING"})
        
        # 1. Reasoning (Ollama LLM)
        try:
            from app.conversation.intent_analysis import IntentAnalyzer
            from app.conversation.retrieval_planner import RetrievalPlanner
            analyzer = IntentAnalyzer()
            planner = RetrievalPlanner()
            intent = analyzer.analyze(text_query)
            categories, budget = planner.plan(intent)
            
            res_memories = []
            for category in categories:
                q = MemoryQuery(category=category, subject="user", limit=budget, include_inferred=True)
                res = memory_runtime.recall(q)
                res_memories.extend(res.memories)
                
            warm_profile_block = MemoryContextBuilder.build_context(res_memories, max_chars=6000, limit=budget)
        except Exception as mem_err:
            logger.error(f"Failed to build memory profile: {mem_err}")
            warm_profile_block = ""
        import os
        import datetime
        now = datetime.datetime.now()
        current_date = now.strftime("%A, %B %d, %Y")
        current_time = now.strftime("%I:%M %p")
        time_context = f"\n\n=== TEMPORAL & ENVIRONMENT REALITY ===\n- Current Date: {current_date}\n- Current Time: {current_time}\n"
        location = os.getenv("LOCAL_LOCATION")
        if location:
            time_context += f"- Current Location: {location}\n"
        time_context += "======================================\n"
        
        import time
        final_instruction = get_system_instruction() + time_context + f"\n\n<!-- cache_bypass: {time.time()} -->"
        if warm_profile_block:
            final_instruction += "\n\n" + warm_profile_block
            
        docs_context = get_all_documents_text_context()
        if docs_context:
            final_instruction += "\n\n=== UPLOADED DOCUMENTS CONTEXT ===\n" + docs_context + "\n=================================="
            
        response_text = await ConversationEngine.run_text_turn(
            system_prompt=final_instruction,
            text_query=text_query,
            websocket=websocket
        )
        if not response_text:
            logger.error(f"[SESSION {session.session_id}] Generation failure: empty response from model.")
            try:
                debug_path = r"C:\Users\JARVIS\.gemini\antigravity-ide\brain\05416677-6b3f-44a9-ab02-29fddfedefe5\scratch\failed_prompt.txt"
                with open(debug_path, "w", encoding="utf-8") as f:
                    f.write(f"=== SYSTEM PROMPT ===\n{final_instruction}\n\n=== USER QUERY ===\n{text_query}\n")
            except Exception as debug_err:
                logger.error(f"Failed to write debug file: {debug_err}")
                
            await safe_send_json(websocket, {
                "type": "system",
                "status": "generation_failure",
                "message": "Generation failed: the model returned an empty response."
            })
            session.end_turn(final_text="")
            return
            
        # Log response safely to console (prevent UnicodeEncodeError on Windows console)
        safe_response_log = response_text.encode('ascii', errors='replace').decode('ascii')
        logger.info(f"Ollama response: {safe_response_log}")
        print(f"🤖 [SENTRI TEXT]: {response_text}\n", flush=True)
        session.end_turn(final_text=response_text)
        
        # Log text output to frontend
        await safe_send_json(websocket, {"type": "text", "data": response_text})
        
    except Exception as e:
        logger.error(f"Error in local text processing turn: {e}")
        session.speaking = False
    finally:
        await safe_send_json(websocket, {"type": "state", "state": "READY"})

@router.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    await websocket.accept()
    logger.info("Frontend client connected to local /ws/voice WebSocket")
    
    # Initialize focused ConversationSession
    session = ConversationSession(session_id=f"voice_session_{int(time.time())}")
    client_sample_rate = 16000
    
    # Reset runtime state to READY on connection
    runtime_store.set_state(RuntimeState.READY)
    runtime_store.update_activity()
    
    # Notify frontend of clean connection
    await safe_send_json(websocket, {"type": "system", "message": "Sentri Local Mode Connected (V2)"})
    
    # Listeners for standby state broadcasts
    def on_standby_entered():
        asyncio.create_task(safe_send_json(websocket, {"type": "state", "state": "STANDBY"}))

    def on_standby_exited():
        asyncio.create_task(safe_send_json(websocket, {"type": "state", "state": "READY"}))

    runtime_events.on("STANDBY_ENTERED", on_standby_entered)
    runtime_events.on("STANDBY_EXITED", on_standby_exited)

    # Inactivity checker task
    async def inactivity_checker():
        while True:
            try:
                await asyncio.sleep(10)
                if runtime_store.state not in (RuntimeState.STANDBY, RuntimeState.WAKING):
                    elapsed = time.time() - runtime_store.last_activity_time
                    if elapsed >= STANDBY_TIMEOUT_SECONDS:
                        logger.info(f"[INACTIVITY] {STANDBY_TIMEOUT_SECONDS}s of idle. Entering standby.")
                        runtime_service.standby()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Inactivity checker error: {e}")

    inactivity_task = asyncio.create_task(inactivity_checker())

    try:
        while True:
            message = await websocket.receive()
            
            if message.get("type") == "websocket.disconnect":
                raise WebSocketDisconnect()
                
            # Standby wake-up guard
            if runtime_store.state in (RuntimeState.STANDBY, RuntimeState.WAKING):
                is_wake_trigger = False
                if runtime_store.state == RuntimeState.STANDBY and "text" in message and message["text"]:
                    try:
                        payload = json.loads(message["text"])
                        p_type = payload.get("type")
                        cmd_text = payload.get("text", "").upper().strip()
                        if p_type == "wake_word":
                            is_wake_trigger = True
                        elif p_type == "command" and cmd_text in ("EXIT_STANDBY", "WAKE", "EXIT standby"):
                            is_wake_trigger = True
                        elif p_type == "governance" and payload.get("command") == "exit_standby":
                            is_wake_trigger = True
                    except Exception:
                        pass
                
                if is_wake_trigger:
                    logger.info("Wake word/command received. Waking up.")
                    runtime_store.update_activity()
                    asyncio.create_task(runtime_service.wake(websocket))
                continue
            else:
                runtime_store.update_activity()

            # Process text messages/payloads
            if "text" in message and message["text"]:
                try:
                    payload = json.loads(message["text"])
                    p_type = payload.get("type")
                    
                    if p_type == "config":
                        client_sample_rate = payload.get("sampleRate", 16000)
                        logger.info(f"Client sample rate configured: {client_sample_rate} Hz")
                        
                    elif p_type == "command":
                        cmd_text = payload.get("text", "")
                        if cmd_text:
                            if cmd_text.upper().strip() == "ENTER_STANDBY":
                                runtime_service.standby()
                            elif cmd_text.upper().strip() == "EXIT_STANDBY":
                                asyncio.create_task(runtime_service.wake(websocket))
                            else:
                                # Intercept and process local text queries (which still works)
                                asyncio.create_task(process_user_text_turn(cmd_text, websocket, session))
                                
                    elif p_type == "governance":
                        cmd = payload.get("command")
                        logger.info(f"Governance command received: {cmd}")
                        
                        if cmd == "pause":
                            from app.tasks.task_manager import pause_all_tasks
                            pause_all_tasks()
                        elif cmd == "resume":
                            from app.tasks.task_manager import resume_all_tasks
                            resume_all_tasks()
                        elif cmd == "stop":
                            from app.tasks.task_manager import stop_all_tasks
                            stop_all_tasks()
                            session.speaking = False
                            await safe_send_json(websocket, {"type": "interrupt"})
                        elif cmd == "enter_standby":
                            runtime_service.standby()
                        elif cmd == "exit_standby":
                            asyncio.create_task(runtime_service.wake(websocket))
                            
                    elif p_type == "turn_complete":
                        audio_turn_data = session.consume_speech_buffer()
                        if len(audio_turn_data) > 0:
                            # Trigger processing of this voice turn
                            asyncio.create_task(process_user_turn(audio_turn_data, websocket, session))
                            
                except WebSocketDisconnect:
                    raise
                except Exception as text_err:
                    logger.error(f"Error parsing json payload: {text_err}")

            # Process incoming binary audio bytes
            elif "bytes" in message and message["bytes"]:
                raw_audio = message["bytes"]
                if len(raw_audio) > 0 and len(raw_audio) % 2 == 0:
                    # Accumulate raw audio bytes inside the session
                    session.append_audio(raw_audio)
                
    except WebSocketDisconnect:
        logger.info("Frontend WebSocket client disconnected cleanly.")
    except Exception as e:
        logger.error(f"Error in websocket loop: {e}")
    finally:
        inactivity_task.cancel()
        runtime_events.off("STANDBY_ENTERED", on_standby_entered)
        runtime_events.off("STANDBY_EXITED", on_standby_exited)
        try:
            from starlette.websockets import WebSocketState
            if websocket.client_state != WebSocketState.DISCONNECTED:
                await websocket.close()
        except Exception:
            pass
