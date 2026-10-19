import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True, slots=True)
class AgentSettings:
    gcp_project: str
    gcp_location: str
    model_id: str


@dataclass(frozen=True, slots=True)
class GatewaySettings:
    mcp_url: str
    llm_url: str
    api_token: str


@lru_cache
def get_agent_settings() -> AgentSettings:
    return AgentSettings(
        gcp_project=os.environ["GOOGLE_CLOUD_PROJECT"],
        gcp_location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
        model_id=os.environ.get("AGENT_MODEL_ID", "claude-sonnet-4-6"),
    )


@lru_cache
def get_gateway_settings() -> GatewaySettings:
    return GatewaySettings(
        mcp_url=os.environ.get("MCP_GATEWAY_URL", "https://llm-gateway.example.com/mcp"),
        llm_url=os.environ.get("LLM_GATEWAY_URL", "https://llm-gateway.example.com/v1"),
        api_token=os.environ["LLM_GATEWAY_TOKEN"],
    )
