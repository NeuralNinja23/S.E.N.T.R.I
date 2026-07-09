import json
import asyncio
import time
import re
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import DATABASE_PATH, STANDBY_TIMEOUT_SECONDS, SENTINEL_SYSTEM_INSTRUCTION
from app.services.logger import get_logger
from app.memory.graph import GraphMemoryStore
from app.memory.graph_ops import build_warm_profile, format_warm_profile_block
from app.runtime.runtime_state import runtime_store, RuntimeState, runtime_events

from app.conversation.engine import ConversationEngine
from app.api.upload import get_all_documents_text_context

router = APIRouter()
logger = get_logger("websocket")

# Initialize graph memory store pointing to Sentinel.db
memory_store = GraphMemoryStore(DATABASE_PATH)

async def process_user_turn(speech_bytes: bytes, websocket: WebSocket, session_state: dict):
    """Voice turn handler stub (V2 ConversationEngine not integrated)."""
    logger.warning("Voice turn triggered, but Conversation Engine is not integrated.")
    await websocket.send_json({
        "type": "system",
        "status": "conversation_engine_missing",
        "message": "Conversation engine has not been integrated."
    })

async def process_user_text_turn(text_query: str, websocket: WebSocket, session_state: dict):
    """Processes text query directly, returning text reply without TTS."""
    session_state["is_model_speaking"] = True
    try:
        # Send USER log to frontend
        await websocket.send_json({"type": "user", "data": text_query})
        
        # Set UI state to THINKING
        await websocket.send_json({"type": "state", "state": "THINKING"})
        
        # 1. Reasoning (Ollama LLM)
        try:
            profile = build_warm_profile(memory_store, user_max_chars=4000, directives_max_chars=2000)
            warm_profile_block = format_warm_profile_block(profile)
        except Exception as mem_err:
            logger.error(f"Failed to build warm profile: {mem_err}")
            warm_profile_block = ""
            
        import datetime
        current_dt = datetime.datetime.now().strftime("%A, %B %d, %Y, %I:%M %p")
        time_context = f"\n\n[Current Local Time Context]\nTime: {current_dt}\nLocation: Anti Noob Media HQ (Home/Office)\n"
        
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
            session_state["is_model_speaking"] = False
            await websocket.send_json({"type": "state", "state": "READY"})
            return
            
        logger.info(f"Ollama response: {response_text}")
        
        # Log full text to frontend (retains <think> blocks for visual display)
        await websocket.send_json({"type": "text", "data": response_text})
        
    except Exception as e:
        logger.error(f"Error in local text processing turn: {e}")
    finally:
        session_state["is_model_speaking"] = False
        try:
            await websocket.send_json({"type": "state", "state": "READY"})
        except Exception:
            pass

@router.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    await websocket.accept()
    logger.info("Frontend client connected to local /ws/voice WebSocket")
    
    session_state = {
        "last_input_time": time.time(),
        "client_sample_rate": None,
        "is_model_speaking": False,
        "is_user_speaking": False,
        "silence_chunks": 0,
        "audioop_state": None
    }
    
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
        from app.runtime.runtime_service import runtime_service
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
                    from app.runtime.runtime_service import runtime_service
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
                        rate = payload.get("sampleRate", 16000)
                        session_state["client_sample_rate"] = rate
                        logger.info(f"Client sample rate configured: {rate} Hz")
                        
                    elif p_type == "command":
                        cmd_text = payload.get("text", "")
                        if cmd_text:
                            if cmd_text.upper().strip() == "ENTER_STANDBY":
                                from app.runtime.runtime_service import runtime_service
                                runtime_service.standby()
                            elif cmd_text.upper().strip() == "EXIT_STANDBY":
                                from app.runtime.runtime_service import runtime_service
                                asyncio.create_task(runtime_service.wake(websocket))
                            else:
                                # Intercept and process local text queries (which still works)
                                asyncio.create_task(process_user_text_turn(cmd_text, websocket, session_state))
                                
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
                            session_state["is_model_speaking"] = False
                            await websocket.send_json({"type": "interrupt"})
                        elif cmd == "enter_standby":
                            from app.runtime.runtime_service import runtime_service
                            runtime_service.standby()
                        elif cmd == "exit_standby":
                            from app.runtime.runtime_service import runtime_service
                            asyncio.create_task(runtime_service.wake(websocket))
                            
                    elif p_type == "turn_complete":
                        logger.warning("Voice turn complete signaled, but Conversation Engine is not integrated.")
                        await websocket.send_json({
                            "type": "system",
                            "status": "conversation_engine_missing",
                            "message": "Conversation engine has not been integrated."
                        })
                            
                except WebSocketDisconnect:
                    raise
                except Exception as text_err:
                    logger.error(f"Error parsing json payload: {text_err}")

            # Process incoming binary audio bytes
            elif "bytes" in message and message["bytes"]:
                logger.warning("Binary audio bytes received, but Conversation Engine is not integrated.")
                await websocket.send_json({
                    "type": "system",
                    "status": "conversation_engine_missing",
                    "message": "Conversation engine has not been integrated."
                })
                
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
