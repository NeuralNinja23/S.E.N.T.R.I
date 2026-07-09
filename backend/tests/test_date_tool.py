import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.genai import types
import asyncio

local_model = LiteLlm(model="ollama_chat/qwen3.5:4b", extra_body={"think": False})

def get_current_date_and_time() -> str:
    """Returns the current local date and time. Use this when the user asks for the date, time, or day."""
    import datetime
    return datetime.datetime.now().strftime("Today is %A, %B %d, %Y. The local time is %I:%M %p.")

test_agent = LlmAgent(
    name="TestAgent",
    model=local_model,
    instruction="You are a helpful assistant. Use tools when asked for the date or time.",
    tools=[get_current_date_and_time]
)

async def test():
    session_service = InMemorySessionService()
    runner = Runner(app_name="test", agent=test_agent, session_service=session_service, artifact_service=InMemoryArtifactService())
    await session_service.create_session(app_name="test", user_id="u", session_id="s")
    content = types.Content(role='user', parts=[types.Part.from_text(text="What is the date today?")])
    print("Running agent with date tool...")
    async for event in runner.run_async(session_id="s", user_id="u", new_message=content):
        if event.is_final_response():
            print("Final Response:", event.content.parts[0].text)

if __name__ == "__main__":
    asyncio.run(test())
