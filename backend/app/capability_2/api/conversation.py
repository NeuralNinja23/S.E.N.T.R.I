import asyncio
import time
import datetime
import os
import logging
from fastapi import WebSocket
from starlette.websockets import WebSocketState

from app.config import get_system_instruction
from app.runtime.runtime_state import runtime_store, RuntimeState
from app.capability_2.core.session import ConversationSession
from app.capability_2.core.engine import ConversationEngine
from app.capability_2.routing.intent_analysis import IntentAnalyzer
from app.capability_2.routing.retrieval_planner import RetrievalPlanner

# Import API operations from Capability 1
from app.capability_1.api.memory import handle_memory_erasure, retrieve_memory_context
from app.capability_1.api.upload import get_all_documents_text_context

logger = logging.getLogger("conversation_api")

conversation_engine = ConversationEngine()
_intent_analyzer = IntentAnalyzer()
_retrieval_planner = RetrievalPlanner()


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


async def process_user_turn(
    speech_bytes: bytes, websocket: WebSocket, session: ConversationSession
):
    """Processes speech input with MiniOmni2, tracking TTFT and TTFA latency metrics."""
    session.start_turn()
    try:
        # Set UI state to THINKING
        await safe_send_json(websocket, {"type": "state", "state": "THINKING"})

        # Helper generator yielding collected speech bytes
        async def audio_generator():
            yield speech_bytes

        logger.info(
            f"[SESSION {session.session_id}] Sending speech turn to ConversationEngine..."
        )
        runtime_store.set_state(RuntimeState.THINKING)
        response_generator = conversation_engine.run_voice_turn(
            audio_generator(), history=session.conversation_history
        )

        first_chunk = True
        accumulated_text = []

        async for chunk in response_generator:
            if not session.speaking:
                logger.info(
                    f"[SESSION {session.session_id}] Speech turn aborted/interrupted by governance."
                )
                break

            if (
                chunk.get("type") == "system"
                and chunk.get("status") == "conversation_engine_missing"
            ):
                await safe_send_json(websocket, chunk)
                break

            if first_chunk:
                # Set UI state back to READY for streaming reply
                await safe_send_json(websocket, {"type": "state", "state": "READY"})
                runtime_store.set_state(RuntimeState.SPEAKING)
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
        runtime_store.set_state(RuntimeState.READY)
        await safe_send_json(websocket, {"type": "state", "state": "READY"})


async def process_user_text_turn(
    text_query: str, websocket: WebSocket, session: ConversationSession
):
    """Processes text query directly, returning text reply without TTS."""
    session.start_turn()
    runtime_store.set_state(RuntimeState.THINKING)
    session.append_user_turn(text_query)
    try:
        # Send USER log to frontend
        print(f"\n\n⌨️  [USER TEXT]: {text_query}\n", flush=True)
        await safe_send_json(websocket, {"type": "user", "data": text_query})

        # Delegate memory erasure handling to Capability 1 Memory API
        erasure_response = handle_memory_erasure(text_query)
        if erasure_response is not None:
            await safe_send_json(
                websocket, {"type": "text", "data": erasure_response}
            )
            await safe_send_json(websocket, {"type": "state", "state": "READY"})
            session.end_turn(final_text=erasure_response)
            return

        # Set UI state to THINKING
        await safe_send_json(websocket, {"type": "state", "state": "THINKING"})

        # 1. Reasoning (Ollama LLM)
        try:
            intent = _intent_analyzer.analyze(text_query)
            categories, budget = _retrieval_planner.plan(intent)

            # Delegate memory retrieval and formatting to Capability 1 Memory API
            warm_profile_block = retrieve_memory_context(categories, budget)
        except Exception as planning_err:
            logger.error(f"Failed in planning/retrieval: {planning_err}")
            warm_profile_block = ""

        now = datetime.datetime.now()
        current_date = now.strftime("%A, %B %d, %Y")
        current_time = now.strftime("%I:%M %p")
        time_context = (
            f"\n\n=== TEMPORAL & ENVIRONMENT REALITY ===\n"
            f"- Current Date: {current_date}\n"
            f"- Current Time: {current_time}\n"
        )
        location = os.getenv("LOCAL_LOCATION")
        if location:
            time_context += f"- Current Location: {location}\n"
        time_context += "======================================\n"

        final_instruction = (
            get_system_instruction()
            + time_context
            + f"\n\n<!-- cache_bypass: {time.time()} -->"
        )
        if warm_profile_block:
            final_instruction += "\n\n" + warm_profile_block

        # Get uploaded document context from Capability 1 Upload API
        docs_context = get_all_documents_text_context()
        if docs_context:
            final_instruction += (
                "\n\n=== UPLOADED DOCUMENTS CONTEXT ===\n"
                + docs_context
                + "\n=================================="
            )

        response_text = await ConversationEngine.run_text_turn(
            system_prompt=final_instruction, text_query=text_query, websocket=websocket
        )
        if not response_text:
            logger.error(
                f"[SESSION {session.session_id}] Generation failure: empty response from model."
            )
            await safe_send_json(
                websocket,
                {
                    "type": "system",
                    "status": "generation_failure",
                    "message": "Generation failed: the model returned an empty response.",
                },
            )
            session.end_turn(final_text="")
            return

        # Log response safely to console
        safe_response_log = response_text.encode("ascii", errors="replace").decode(
            "ascii"
        )
        logger.info(f"Ollama response: {safe_response_log}")
        print(f"🤖 [SENTRI TEXT]: {response_text}\n", flush=True)
        session.end_turn(final_text=response_text)

        # Log text output to frontend
        await safe_send_json(websocket, {"type": "text", "data": response_text})

    except Exception as e:
        logger.error(f"Error in local text processing turn: {e}")
        session.speaking = False
    finally:
        runtime_store.set_state(RuntimeState.READY)
        await safe_send_json(websocket, {"type": "state", "state": "READY"})
