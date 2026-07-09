import json
import httpx
import asyncio
import os
import sys
import logging
from app.services.logger import get_logger

# Import ADK elements
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.genai import types

# Inject backend root into path to import agent.py
backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

try:
    from agent import root_agent
except ImportError:
    # Fallback to absolute path import just in case
    import importlib.util
    spec = importlib.util.spec_from_file_location("agent", os.path.join(backend_root, "agent.py"))
    agent_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(agent_mod)
    root_agent = agent_mod.root_agent

logger = get_logger("reasoning_service")

# Initialize ADK runner structures (InMemory Session and Artifacts)
session_service = InMemorySessionService()
artifact_service = InMemoryArtifactService()
runner = Runner(
    app_name="sentinel",
    agent=root_agent,
    session_service=session_service,
    artifact_service=artifact_service
)

class ReasoningService:
    @staticmethod
    def generate(
        system_prompt: str,
        user_content: str,
        temperature: float = 0.0,
        stream: bool = False,
        on_token=None,
        timeout_sec: float = None
    ) -> str:
        """
        Sends a query to the local ADK agent synchronously and returns the generated content.
        """
        # Bind the dynamic system prompt to the agent instruction
        root_agent.instruction = system_prompt
        
        session_id = "default_session"
        user_id = "default_user"
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        async def create_session_sync():
            session = await session_service.get_session(
                app_name="sentinel",
                user_id=user_id,
                session_id=session_id
            )
            if session is None:
                await session_service.create_session(
                    app_name="sentinel",
                    user_id=user_id,
                    session_id=session_id
                )
                
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
        loop.run_until_complete(create_session_sync())
            
        content = types.Content(role='user', parts=[types.Part.from_text(text=user_content)])
        
        try:
            events = runner.run(session_id=session_id, user_id=user_id, new_message=content)
            full_response_parts = []
            for event in events:
                if event.is_final_response():
                    for part in event.content.parts:
                        if part.text:
                            full_response_parts.append(part.text)
                            if on_token:
                                on_token(part.text)
            return "".join(full_response_parts).strip()
        except Exception as e:
            logger.error(f"Failed to communicate with local ADK agent sync: {e}")
            return ""

    @staticmethod
    async def generate_async(
        system_prompt: str,
        user_content: str,
        temperature: float = 0.0,
        stream: bool = False,
        on_token=None,
        timeout_sec: float = None
    ) -> str:
        """
        Asynchronously sends a query to the local ADK agent and returns the generated content.
        """
        # Bind the dynamic system prompt to the agent instruction
        root_agent.instruction = system_prompt
        
        session_id = "default_session"
        user_id = "default_user"
        
        session = await session_service.get_session(
            app_name="sentinel",
            user_id=user_id,
            session_id=session_id
        )
        if session is None:
            await session_service.create_session(
                app_name="sentinel",
                user_id=user_id,
                session_id=session_id
            )
            
        content = types.Content(role='user', parts=[types.Part.from_text(text=user_content)])
        
        try:
            full_response_parts = []
            async for event in runner.run_async(session_id=session_id, user_id=user_id, new_message=content):
                if event.is_final_response():
                    for part in event.content.parts:
                        if part.text:
                            full_response_parts.append(part.text)
                            if on_token:
                                if asyncio.iscoroutinefunction(on_token):
                                    await on_token(part.text)
                                else:
                                    on_token(part.text)
            return "".join(full_response_parts).strip()
        except Exception as e:
            logger.error(f"Failed to communicate with local ADK agent async: {e}")
            return ""
