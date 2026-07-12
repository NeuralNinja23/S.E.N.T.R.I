import json
import asyncio
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import STANDBY_TIMEOUT_SECONDS, SENTINEL_SYSTEM_INSTRUCTION
from app.services.logger import get_logger
from app.runtime.runtime_state import runtime_store, RuntimeState, runtime_events
from app.runtime.runtime_service import runtime_service

from app.conversation import ConversationEngine, ConversationSession
from app.api.upload import get_all_documents_text_context

router = APIRouter()
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
        await websocket.send_json({"type": "state", "state": "THINKING"})
        
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
                await websocket.send_json(chunk)
                break
                
            if first_chunk:
                # Set UI state back to READY for streaming reply
                await websocket.send_json({"type": "state", "state": "READY"})
                first_chunk = False
                
            if chunk["type"] == "audio":
                session.metrics.record_first_audio()
                await websocket.send_bytes(chunk["data"])
                await asyncio.sleep(0.005)  # Flow control
            elif chunk["type"] == "text":
                session.metrics.record_first_token()
                session.metrics.add_tokens(len(chunk["data"].split()))
                accumulated_text.append(chunk["data"])
                await websocket.send_json({"type": "text", "data": chunk["data"]})
            elif chunk["type"] == "user_transcript":
                session.append_user_turn(chunk["data"])
                await websocket.send_json({"type": "user", "data": chunk["data"]})
                
        final_response = "".join(accumulated_text).strip()
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
        try:
            await websocket.send_json({"type": "state", "state": "READY"})
        except Exception:
            pass

async def process_user_text_turn(text_query: str, websocket: WebSocket, session: ConversationSession):
    """Processes text query directly, returning text reply without TTS."""
    session.start_turn()
    session.append_user_turn(text_query)
    try:
        # Send USER log to frontend
        await websocket.send_json({"type": "user", "data": text_query})
        
        # Set UI state to THINKING
        await websocket.send_json({"type": "state", "state": "THINKING"})
        
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
                q = MemoryQuery(category=category, subject="user", limit=budget, include_inferred=False)
                res = memory_runtime.recall(q)
                res_memories.extend(res.memories)
                
            warm_profile_block = MemoryContextBuilder.build_context(res_memories, max_chars=6000, limit=budget)
        except Exception as mem_err:
            logger.error(f"Failed to build memory profile: {mem_err}")
            warm_profile_block = ""
            
        import os
        import datetime
        current_dt = datetime.datetime.now().strftime("%A, %B %d, %Y, %I:%M %p")
        time_context = f"\n\n=== TEMPORAL & ENVIRONMENT REALITY ===\n- Current Date/Time: {current_dt}\n"
        location = os.getenv("LOCAL_LOCATION")
        if location:
            time_context += f"- Current Location: {location}\n"
        time_context += "======================================\n"
        
        final_instruction = SENTINEL_SYSTEM_INSTRUCTION + time_context
        if warm_profile_block:
            final_instruction += "\n\n" + warm_profile_block
            
        docs_context = get_all_documents_text_context()
        if docs_context:
            final_instruction += "\n\n=== UPLOADED DOCUMENTS CONTEXT ===\n" + docs_context + "\n=================================="
            
        response_text = await ConversationEngine.run_text_turn(
            system_prompt=final_instruction,
            text_query=text_query
        )
        
        if not response_text:
            session.end_turn()
            await websocket.send_json({"type": "state", "state": "READY"})
            return
            
        logger.info(f"Ollama response: {response_text}")
        session.end_turn(final_text=response_text)
        
        # Log full text to frontend (retains <think> blocks for visual display)
        await websocket.send_json({"type": "text", "data": response_text})
        
    except Exception as e:
        logger.error(f"Error in local text processing turn: {e}")
        session.speaking = False
    finally:
        try:
            await websocket.send_json({"type": "state", "state": "READY"})
        except Exception:
            pass

@router.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    await websocket.accept()
    logger.info("Frontend client connected to local /ws/voice WebSocket")
    
    # Initialize focused ConversationSession
    session = ConversationSession(session_id=f"voice_session_{int(time.time())}")
    client_sample_rate = 16000
    
    # Notify frontend of clean connection
    await websocket.send_json({"type": "system", "message": "Sentinel Local Mode Connected (V2)"})
    
    # Listeners for standby state broadcasts
    def on_standby_entered():
        asyncio.create_task(websocket.send_json({"type": "state", "state": "STANDBY"}))

    def on_standby_exited():
        asyncio.create_task(websocket.send_json({"type": "state", "state": "READY"}))

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
                            await websocket.send_json({"type": "interrupt"})
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
