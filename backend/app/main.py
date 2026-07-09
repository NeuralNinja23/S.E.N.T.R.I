from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
import asyncio
import logging

# Filter out /api/system-stats from uvicorn access logs
class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Check in the formatted message
        msg = record.getMessage()
        if "/api/system-stats" in msg:
            return False
        # Also check raw arguments just in case
        if record.args:
            for arg in record.args:
                if isinstance(arg, str) and "/api/system-stats" in arg:
                    return False
        return True

logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

from app.api.websocket import router as websocket_router
from app.api.system_stats import router as system_stats_router
from app.api.upload import router as upload_router
from app.runtime.task_runtime import task_worker_loop

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start MiniOmni2 Flask model server if not already running
    import subprocess
    import socket
    import os
    import time
    
    def is_port_open(ip: str, port: int) -> bool:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        try:
            s.connect((ip, port))
            s.close()
            return True
        except Exception:
            return False

    miniomni_proc = None
    if not is_port_open("127.0.0.1", 60808):
        miniomni_dir = "C:\\Users\\JARVIS\\Desktop\\GenxAI Labz\\MiniOmni 2"
        python_exe = os.path.join(miniomni_dir, "venv", "Scripts", "python.exe")
        server_py = os.path.join(miniomni_dir, "server.py")
        
        logging.getLogger("uvicorn").info("[MINI-OMNI2] Starting model server in background...")
        try:
            miniomni_proc = subprocess.Popen(
                [python_exe, server_py, "--ip", "127.0.0.1", "--port", "60808"],
                cwd=miniomni_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            # Wait for it to become healthy
            for _ in range(30):
                if is_port_open("127.0.0.1", 60808):
                    logging.getLogger("uvicorn").info("[MINI-OMNI2] Model server started successfully.")
                    break
                await asyncio.sleep(0.5)
        except Exception as e:
            logging.getLogger("uvicorn").error(f"[MINI-OMNI2] Failed to start model server: {e}")

    app.state.miniomni_proc = miniomni_proc

    # Start the background task worker loop for long-running tools
    task_loop = asyncio.create_task(task_worker_loop())

    # ThreadPool for synchronous tools
    app.state.tool_executor = ThreadPoolExecutor(max_workers=8)

    # Build the World Model in a background thread (non-blocking)
    def _build_world_model():
        try:
            from app.world_model.world_model_service import WorldModelService
            service = WorldModelService()
            summary = service.build_world_model()
            logging.getLogger("uvicorn").info(
                f"[WORLD MODEL] Built: {summary['projects_found']} projects, "
                f"{summary['folders_found']} folders, {summary['files_found']} files "
                f"in {summary['duration_seconds']}s"
            )
        except Exception as e:
            logging.getLogger("uvicorn").error(f"[WORLD MODEL] Build failed: {e}")

    import threading
    wm_thread = threading.Thread(target=_build_world_model, daemon=True)
    wm_thread.start()

    # Start the periodic world sync loop (every 3 hours)
    async def world_sync_loop():
        # Wait 30 seconds after startup before the first check
        await asyncio.sleep(30)
        from app.world_model.world_sync_service import WorldSyncService
        sync_service = WorldSyncService()
        while True:
            try:
                if sync_service.is_paused():
                    logging.getLogger("uvicorn").info("[WORLD SYNC] Sync is paused (Sentinel is in standby). Skipping periodic execution.")
                else:
                    # Run sync in thread pool to prevent blocking the event loop
                    summary = await asyncio.to_thread(sync_service.sync)
                    logging.getLogger("uvicorn").info(
                        f"[WORLD SYNC] Periodic sync completed: "
                        f"Added {summary['files_added']}, Deleted {summary['files_deleted']}, "
                        f"Modified {summary['files_modified']} files in {summary['duration_seconds']}s"
                    )
            except Exception as e:
                logging.getLogger("uvicorn").error(f"[WORLD SYNC] Sync failed: {e}")
            await asyncio.sleep(10800)

    sync_task = asyncio.create_task(world_sync_loop())

    # Start the Desktop Watchdog service (realtime awareness)
    from app.world_model.desktop_watchdog_service import DesktopWatchdogService
    watchdog_service = DesktopWatchdogService()
    try:
        watchdog_service.start()
    except Exception as e:
        logging.getLogger("uvicorn").error(f"[WATCHDOG] Failed to start: {e}")

    yield
    
    # Shutdown cleanly
    try:
        watchdog_service.stop()
    except Exception as e:
        logging.getLogger("uvicorn").error(f"[WATCHDOG] Failed to stop: {e}")
    
    # Terminate MiniOmni2 model server if we started it
    if hasattr(app.state, "miniomni_proc") and app.state.miniomni_proc:
        logging.getLogger("uvicorn").info("[MINI-OMNI2] Terminating model server...")
        try:
            app.state.miniomni_proc.terminate()
            app.state.miniomni_proc.wait(timeout=5.0)
        except Exception as e:
            logging.getLogger("uvicorn").error(f"[MINI-OMNI2] Failed to cleanly terminate: {e}")

    sync_task.cancel()
    task_loop.cancel()
    app.state.tool_executor.shutdown(wait=True)

app = FastAPI(title="Sentinel Voice API", lifespan=lifespan)

# Allow all origins for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(websocket_router)
app.include_router(system_stats_router)
app.include_router(upload_router)

@app.get("/")
def read_root():
    return {"message": "Sentinel Voice Backend Online"}

