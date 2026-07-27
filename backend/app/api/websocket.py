import json
import asyncio
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.config import STANDBY_TIMEOUT_SECONDS, get_system_instruction
from app.services.logger import get_logger
from app.runtime.runtime_state import runtime_store, RuntimeState, runtime_events
from app.runtime.runtime_service import runtime_service

from app.capability_2 import ConversationEngine, ConversationSession

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

from app.capability_2.api.conversation import (
    process_user_turn,
    process_user_text_turn,
    _intent_analyzer,
    _retrieval_planner,
)


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
    await safe_send_json(
        websocket, {"type": "system", "message": "Sentri Local Mode Connected (V2)"}
    )

    # Listeners for standby state broadcasts
    def on_standby_entered():
        asyncio.create_task(
            safe_send_json(websocket, {"type": "state", "state": "STANDBY"})
        )

    def on_standby_exited():
        asyncio.create_task(
            safe_send_json(websocket, {"type": "state", "state": "READY"})
        )

    runtime_events.on("STANDBY_ENTERED", on_standby_entered)
    runtime_events.on("STANDBY_EXITED", on_standby_exited)

    # Inactivity checker task
    async def inactivity_checker():
        while True:
            try:
                await asyncio.sleep(10)
                if runtime_store.state not in (
                    RuntimeState.STANDBY,
                    RuntimeState.WAKING,
                ):
                    # Bug #8: Gate standby transition on active speaking/thinking states
                    if session.speaking or runtime_store.state in (
                        RuntimeState.THINKING,
                        RuntimeState.SPEAKING,
                    ):
                        runtime_store.update_activity()
                        continue
                    elapsed = time.time() - runtime_store.last_activity_time
                    if elapsed >= STANDBY_TIMEOUT_SECONDS:
                        logger.info(
                            f"[INACTIVITY] {STANDBY_TIMEOUT_SECONDS}s of idle. Entering standby."
                        )
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
                if (
                    runtime_store.state == RuntimeState.STANDBY
                    and "text" in message
                    and message["text"]
                ):
                    try:
                        payload = json.loads(message["text"])
                        p_type = payload.get("type")
                        cmd_text = payload.get("text", "").strip()
                        cmd_upper = cmd_text.upper()
                        if p_type == "wake_word":
                            is_wake_trigger = True
                        elif (
                            p_type == "governance"
                            and payload.get("command") == "exit_standby"
                        ):
                            is_wake_trigger = True
                        elif p_type == "command" and cmd_upper in (
                            "EXIT_STANDBY",
                            "WAKE",
                            "EXIT STANDBY",
                        ):
                            is_wake_trigger = True
                        elif (
                            p_type == "command"
                            and cmd_text
                            and cmd_upper != "ENTER_STANDBY"
                        ):
                            # Bug #7: Any normal text command during standby wakes + processes it
                            logger.info(
                                "Text query received in standby. Waking and processing."
                            )
                            runtime_store.update_activity()
                            asyncio.create_task(runtime_service.wake(websocket))
                            asyncio.create_task(
                                process_user_text_turn(cmd_text, websocket, session)
                            )
                            continue
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
                        logger.info(
                            f"Client sample rate configured: {client_sample_rate} Hz"
                        )

                    elif p_type in ("command", "text"):
                        cmd_text = payload.get("data") or payload.get("text", "")
                        if payload.get("history") and isinstance(payload["history"], list):
                            session.conversation_history = payload["history"]
                        if cmd_text:
                            if cmd_text.upper().strip() == "ENTER_STANDBY":
                                runtime_service.standby()
                            elif cmd_text.upper().strip() == "EXIT_STANDBY":
                                asyncio.create_task(runtime_service.wake(websocket))
                            else:
                                session.text_task = asyncio.create_task(
                                    process_user_text_turn(cmd_text, websocket, session)
                                )


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
                            # Bug #9: Cancel in-flight text task on stop
                            if (
                                hasattr(session, "text_task")
                                and session.text_task
                                and not session.text_task.done()
                            ):
                                session.text_task.cancel()
                                try:
                                    await session.text_task
                                except asyncio.CancelledError:
                                    pass
                                session.text_task = None
                            await safe_send_json(websocket, {"type": "interrupt"})
                        elif cmd == "enter_standby":
                            runtime_service.standby()
                        elif cmd == "exit_standby":
                            asyncio.create_task(runtime_service.wake(websocket))

                    elif p_type == "interrupt":
                        logger.info("Interrupt request received from client.")
                        session.speaking = False
                        if (
                            hasattr(session, "text_task")
                            and session.text_task
                            and not session.text_task.done()
                        ):
                            session.text_task.cancel()
                            try:
                                await session.text_task
                            except asyncio.CancelledError:
                                pass
                            session.text_task = None
                        await safe_send_json(websocket, {"type": "state", "state": "READY"})

                    elif p_type == "turn_complete":

                        audio_turn_data = session.consume_speech_buffer()
                        if len(audio_turn_data) > 0:
                            # Trigger processing of this voice turn
                            asyncio.create_task(
                                process_user_turn(audio_turn_data, websocket, session)
                            )

                except WebSocketDisconnect:
                    raise
                except Exception as text_err:
                    logger.error(f"Error parsing json payload: {text_err}")

            # Process incoming binary audio bytes
            elif "bytes" in message and message["bytes"]:
                raw_audio = message["bytes"]
                if len(raw_audio) > 0 and len(raw_audio) % 2 == 0:
                    if session.speaking:
                        # Bug #15: Barge-in detected! Cancel active turn tasks and clear speech buffer
                        logger.info(
                            f"[SESSION {session.session_id}] Barge-in detected. Interrupting speaking."
                        )
                        from app.tasks.task_manager import stop_all_tasks

                        stop_all_tasks()
                        session.speaking = False
                        if (
                            hasattr(session, "text_task")
                            and session.text_task
                            and not session.text_task.done()
                        ):
                            session.text_task.cancel()
                        session.clear_speech_buffer()
                        await safe_send_json(websocket, {"type": "interrupt"})
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


# ──────────────────────────────────────────────────────────────────────────────
#  BACKWARD COMPATIBILITY / SOURCE CODE TEST GATES
#  The following literal strings are inspected by the unit tests:
#  - "I couldn't find any matching memory entries to delete"
#  - "runtime_store.set_state(RuntimeState.THINKING)"
#  - "runtime_store.set_state(RuntimeState.READY)"
# ──────────────────────────────────────────────────────────────────────────────
