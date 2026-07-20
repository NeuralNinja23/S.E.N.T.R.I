import time
import asyncio
import logging
from app.runtime.runtime_state import runtime_store, runtime_events, RuntimeState

logger = logging.getLogger("runtime_service")


class RuntimeService:
    def standby(self):
        if runtime_store.state == RuntimeState.STANDBY:
            return
        logger.info("Transitioning READY -> STANDBY")
        runtime_store.set_state(RuntimeState.STANDBY)
        runtime_store.standby_entered_at = time.time()

        # Emit event
        runtime_events.emit("STANDBY_ENTERED")

    async def wake(self, websocket=None):
        if runtime_store.state != RuntimeState.STANDBY:
            return
        logger.info("Transitioning STANDBY -> WAKING")
        runtime_store.set_state(RuntimeState.WAKING)

        # Notify websocket client of WAKING state
        if websocket:
            try:
                await websocket.send_json({"type": "state", "state": "WAKING"})
            except Exception as e:
                logger.warning(f"Could not send WAKING state to client: {e}")

        # Intentional 1-second delay
        await asyncio.sleep(1.0)

        duration = round(time.time() - runtime_store.standby_entered_at, 2)
        logger.info(f"Transitioning WAKING -> READY (standby duration: {duration}s)")

        runtime_store.set_state(RuntimeState.READY)

        # Emit event
        runtime_events.emit("STANDBY_EXITED")

        # Notify websocket client of READY state
        if websocket:
            try:
                await websocket.send_json({"type": "state", "state": "READY"})
            except Exception as e:
                logger.warning(f"Could not send READY state to client: {e}")

    def speaking(self) -> bool:
        if runtime_store.state in (RuntimeState.STANDBY, RuntimeState.WAKING):
            logger.warning(
                f"Speaking state denied. Currently in {runtime_store.state} state."
            )
            return False
        runtime_store.set_state(RuntimeState.SPEAKING)
        runtime_events.emit("SPEAKING")
        return True


runtime_service = RuntimeService()
