import subprocess
import socket
import time
import os
import asyncio
import httpx
from enum import Enum
from app.services.logger import get_logger
from app.config import MINIOMNI_HOME, MINIOMNI_SERVER, MINIOMNI_PORT, MINIOMNI_PYTHON

logger = get_logger("model_runtime")

class InferenceRuntimeState(str, Enum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    LOADING_MODEL = "LOADING_MODEL"
    READY = "READY"
    FAILED = "FAILED"
    STOPPING = "STOPPING"

class InferenceRuntimeManager:
    """
    Manages process lifecycles, monitoring, and state tracking for inference models.
    """
    
    def __init__(self):
        self.proc = None
        self.state = InferenceRuntimeState.STOPPED
        
    def _is_port_open(self, ip: str, port: int) -> bool:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        try:
            s.connect((ip, port))
            s.close()
            return True
        except Exception:
            return False
            
    async def check_health(self) -> bool:
        """
        Queries the model endpoint to verify HTTP availability and warm-up readiness.
        """
        ip_addr = MINIOMNI_SERVER.replace("http://", "").replace("https://", "")
        if not self._is_port_open(ip_addr, MINIOMNI_PORT):
            return False
            
        url = f"{MINIOMNI_SERVER}:{MINIOMNI_PORT}/chat"
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(url)
                # GET is 405 Method Not Allowed (meaning Flask is up and model warm-up succeeded)
                return resp.status_code == 405
        except Exception:
            return False
            
    async def start(self):
        """
        Starts the MiniOmni2 background model server if not already running.
        """
        ip_addr = MINIOMNI_SERVER.replace("http://", "").replace("https://", "")
        
        # Check if already running (possibly orphaned or started externally)
        if await self.check_health():
            logger.info(f"Model server is already running and healthy on port {MINIOMNI_PORT}.")
            self.state = InferenceRuntimeState.READY
            return
            
        self.state = InferenceRuntimeState.STARTING
        python_exe = os.path.join(MINIOMNI_HOME, MINIOMNI_PYTHON)
        server_py = os.path.join(MINIOMNI_HOME, "server.py")
        
        logger.info(f"Starting MiniOmni2 model server daemon from {MINIOMNI_HOME}...")
        self.state = InferenceRuntimeState.LOADING_MODEL
        try:
            self.proc = subprocess.Popen(
                [python_exe, server_py, "--ip", ip_addr, "--port", str(MINIOMNI_PORT)],
                cwd=MINIOMNI_HOME,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            # Wait for healthcheck success
            for i in range(40):
                if await self.check_health():
                    logger.info("MiniOmni2 model server daemon is fully healthy and ready.")
                    self.state = InferenceRuntimeState.READY
                    return
                await asyncio.sleep(0.5)
            logger.error("MiniOmni2 model server failed to pass healthcheck in time.")
            self.state = InferenceRuntimeState.FAILED
        except Exception as e:
            logger.error(f"Failed to spawn MiniOmni2 model server process: {e}")
            self.state = InferenceRuntimeState.FAILED
            
    def stop(self):
        """
        Stops the managed model server.
        """
        if self.proc:
            self.state = InferenceRuntimeState.STOPPING
            logger.info("Terminating MiniOmni2 model server daemon process...")
            try:
                self.proc.terminate()
                self.proc.wait(timeout=5.0)
                logger.info("MiniOmni2 model server daemon stopped cleanly.")
                self.state = InferenceRuntimeState.STOPPED
            except Exception as e:
                logger.error(f"Failed to cleanly terminate MiniOmni2 model server: {e}")
                self.state = InferenceRuntimeState.FAILED
            finally:
                self.proc = None
        else:
            self.state = InferenceRuntimeState.STOPPED

# Expose singleton instance for runtime management
inference_runtime_manager = InferenceRuntimeManager()
