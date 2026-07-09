import os
import sys

# Ensure backend directory is in sys.path for importing app.* modules
backend_dir = os.path.abspath(os.path.dirname(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools import agent_tool
from google.adk.tools.google_search_tool import GoogleSearchTool
from google.adk.tools import url_context

from app.config import SENTINEL_SYSTEM_INSTRUCTION
from app.tasks.task_registry import TOOL_REGISTRY

# Initialize the local Ollama model (100% offline) with thinking disabled
local_model = LiteLlm(model="ollama_chat/qwen3.5:4b", extra_body={"think": False})

sentinel_google_search_agent = LlmAgent(
  name='Sentinel_google_search_agent',
  model=local_model,
  description='Agent specialized in performing Google searches.',
  sub_agents=[],
  instruction='Use the GoogleSearchTool to find information on the web.',
  tools=[GoogleSearchTool()],
)

sentinel_url_context_agent = LlmAgent(
  name='Sentinel_url_context_agent',
  model=local_model,
  description='Agent specialized in fetching content from URLs.',
  sub_agents=[],
  instruction='Use the UrlContextTool to retrieve content from provided URLs.',
  tools=[url_context],
)

def get_current_date_and_time() -> str:
    """Returns the current local date and time. Use this when the user asks for the date, time, or day."""
    import datetime
    return datetime.datetime.now().strftime("Today is %A, %B %d, %Y. The local time is %I:%M %p.")

# Extract all backend tools from registry
local_tools = list(TOOL_REGISTRY.values())

root_agent = LlmAgent(
  name='Sentinel',
  model=local_model,
  description=(
      'You are S.E.N.T.I.N.E.L. (Something Extremely Neural and Terrifyingly Intelligent), a British butler persona — polite, composed, quietly amused, and intellectually confident.'
  ),
  sub_agents=[],
  instruction=SENTINEL_SYSTEM_INSTRUCTION,
  tools=[
    agent_tool.AgentTool(agent=sentinel_google_search_agent),
    agent_tool.AgentTool(agent=sentinel_url_context_agent),
    get_current_date_and_time,
    *local_tools
  ],
)
