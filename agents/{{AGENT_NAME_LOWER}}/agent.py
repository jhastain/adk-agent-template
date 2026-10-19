from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from .config import get_agent_settings, get_gateway_settings
from .prompts import SYSTEM_INSTRUCTION
from .tools import example_tool

_settings = get_agent_settings()
_bifrost = get_gateway_settings()

_model = LiteLlm(
    model=f"openai/{_settings.model_id}",
    api_base=_bifrost.llm_url,
    api_key=_bifrost.api_token,
)

root_agent = Agent(
    model=_model,
    name="{{AGENT_NAME_LOWER}}",
    description="{{AGENT_DISPLAY_NAME}} — describe what this agent does.",
    instruction=SYSTEM_INSTRUCTION,
    tools=[example_tool],
)
