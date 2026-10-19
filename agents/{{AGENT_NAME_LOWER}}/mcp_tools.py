"""MCP gateway integration for ADK agents.

The MCP gateway is the single egress point for every tool this agent can reach.
It provides access to Azure DevOps, Datadog, Sentry, Atlassian, and other
internal tools via a single HTTP endpoint with virtual API keys.

Usage:
    from .mcp_tools import create_gateway_toolset

    toolset = create_gateway_toolset(
        tool_filter=["repo_create_pull_request", "wit_create_work_item"]
    )

    root_agent = Agent(
        tools=[toolset, ...other_tools],
    )

Available tool servers behind the gateway (example roster - replace with yours):
    azure_devops  - repos, PRs, branches, work items, code search
    atlassian     - Jira issues, Confluence pages
    datadog       - monitors, dashboards, metrics
    sentry        - error tracking, issues
    context7      - library documentation lookup
"""

from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

from .config import get_gateway_settings


def create_gateway_toolset(
    tool_filter: list[str] | None = None,
) -> McpToolset:
    """Create an MCP toolset connected to the gateway.

    Args:
        tool_filter: Optional list of tool names to expose. If None, all tools
            from the gateway server are available. Recommended: always filter
            to only the tools your agent needs.

    Returns:
        McpToolset configured for gateway.
    """
    settings = get_gateway_settings()

    params = StreamableHTTPConnectionParams(
        url=settings.mcp_url,
        headers={"Authorization": f"Bearer {settings.api_token}"},  # same gw-key-... key as LLM
    )

    kwargs: dict = {"connection_params": params}
    if tool_filter:
        kwargs["tool_filter"] = tool_filter

    return McpToolset(**kwargs)
