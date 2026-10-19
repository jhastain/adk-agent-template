# Google ADK Agent Patterns Guide

> **Sources**: [Official ADK Documentation](https://adk.dev/), [Google Cloud ADK Docs](https://docs.google.com/gemini-enterprise-agent-platform/build/adk), [ADK Python GitHub](https://github.com/google/adk-python)

---

## 1. Agent Naming Rules

- Must be a **valid Python identifier**: letters, digits, underscores only
- **No hyphens**, spaces, or special characters
- Cannot start with a digit
- Cannot use `"user"` (reserved)
- Must be unique within the agent tree
- **Directory names must also follow these rules** — ADK uses the folder name as the app name

```python
# Valid
LlmAgent(name="weather_agent", ...)
LlmAgent(name="ResearchAssistant", ...)

# Invalid
LlmAgent(name="weather-agent", ...)   # Hyphens
LlmAgent(name="user", ...)            # Reserved
LlmAgent(name="123agent", ...)        # Starts with digit
```

---

## 2. Tool Definitions

ADK auto-generates tool schemas from your Python function signature:

- **Function name** → tool identifier
- **Docstring** → tool description for the LLM
- **Type hints** → parameter types
- **Default values** → optional vs required

```python
def get_weather(city: str) -> dict:
    """Get current weather for a city.

    Args:
        city: Name of the city (e.g., 'London', 'New York')

    Returns:
        Weather data including temperature and conditions
    """
    return {"city": city, "temp": 72, "condition": "sunny"}


def search_articles(
    query: str,
    max_results: int = 10,
    language: str | None = None,
) -> list[dict]:
    """Search for articles matching query.

    Args:
        query: Search terms
        max_results: Maximum number of results (default: 10)
        language: Optional language filter (e.g., 'en', 'es')

    Returns:
        List of article dictionaries
    """
    pass
```

### Async Tools (Parallel Execution)

ADK runs async tools in parallel automatically:

```python
async def get_weather(city: str) -> dict:
    """Get current weather for a single city.

    Args:
        city: Name of the city

    Returns:
        Weather data
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.weather.com/{city}") as resp:
            return await resp.json()
```

### Return Type Best Practice

Return dicts with a `"status"` key for error handling:

```python
def search_database(query: str) -> dict:
    """Query the database safely.

    Args:
        query: Search query

    Returns:
        Dictionary with 'status' and 'results' or 'error'
    """
    try:
        if "DROP" in query.upper():
            return {"status": "error", "error": "Destructive operations not allowed"}
        results = db.execute(query)
        return {"status": "success", "results": results, "count": len(results)}
    except Exception as e:
        return {"status": "error", "error": str(e)}
```

### Avoid Variadic Parameters

`*args` and `**kwargs` are **ignored** by ADK schema generation.

```python
# Bad — LLM cannot use these
def process(*items, **options): ...

# Good — explicit parameters
def process(items: list[str], sort_by: str = "name"): ...
```

---

## 3. Multi-Agent Patterns

### Sequential Agents

Execute sub-agents in strict order:

```python
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.agents.llm_agent import LlmAgent

researcher = LlmAgent(
    name="researcher",
    model="gemini-2.5-flash",
    instruction="Research the topic and write findings.",
    tools=[google_search],
    output_key="research_findings",
)

writer = LlmAgent(
    name="writer",
    model="gemini-2.5-flash",
    instruction="Read {research_findings} and write a blog post.",
    output_key="blog_post",
)

root_agent = SequentialAgent(
    name="blog_pipeline",
    sub_agents=[researcher, writer],
)
```

### Parallel Agents

Execute sub-agents concurrently — each must write to a **unique state key**:

```python
from google.adk.agents.parallel_agent import ParallelAgent

energy_researcher = LlmAgent(
    name="energy_researcher",
    model="gemini-2.5-flash",
    instruction="Research renewable energy.",
    output_key="energy_result",
)

ev_researcher = LlmAgent(
    name="ev_researcher",
    model="gemini-2.5-flash",
    instruction="Research electric vehicles.",
    output_key="ev_result",
)

parallel_research = ParallelAgent(
    name="parallel_research",
    sub_agents=[energy_researcher, ev_researcher],
)

merger = LlmAgent(
    name="merger",
    model="gemini-2.5-flash",
    instruction="Combine {energy_result} and {ev_result} into a report.",
)

root_agent = SequentialAgent(
    name="research_pipeline",
    sub_agents=[parallel_research, merger],
)
```

### AgentTool (Sub-Agent as Tool)

Wrap a sub-agent so the parent can invoke it like a function tool:

```python
from google.adk.tools.agent_tool import AgentTool

positive_critic = LlmAgent(
    name="positive_critic",
    model="gemini-2.5-flash",
    instruction="Provide positive feedback on the given text.",
)

negative_critic = LlmAgent(
    name="negative_critic",
    model="gemini-2.5-flash",
    instruction="Provide constructive criticism on the given text.",
)

editor = LlmAgent(
    name="editor",
    model="gemini-2.5-flash",
    instruction="""Review the user's draft.
    Use positive_critic and negative_critic tools to get feedback,
    then synthesize a complete review.""",
    tools=[
        AgentTool(agent=positive_critic),
        AgentTool(agent=negative_critic),
    ],
)
```

### When to Use Sub-Agents vs Tools

| Sub-Agents | Tools |
|---|---|
| Multi-step reasoning | Single operation |
| Needs its own tools | Single API call |
| Modular, reusable capability | Stateless function |
| Complex isolated logic | Simple integration |

---

## 4. Agent Configuration

### Model and Generation Config

```python
from google.genai import types

agent = LlmAgent(
    name="fact_checker",
    model="gemini-2.5-flash",
    instruction="Verify facts and provide citations.",
    generate_content_config=types.GenerateContentConfig(
        temperature=0.1,
        max_output_tokens=1000,
        top_p=0.95,
    ),
)
```

**Temperature guide**: 0.0-0.2 for factual tasks, 0.5-0.7 balanced, 0.8-1.0 creative.

---

## 5. Session and State Management

### State Scopes

| Prefix | Scope | Use Case |
|---|---|---|
| (none) | Current session | Task progress, flags |
| `user:` | All sessions for user | Preferences, profile |
| `app:` | All users/sessions | Global settings |
| `temp:` | Current invocation only | Intermediate values |

```python
session.state["current_step"] = "verification"
session.state["user:preferred_language"] = "fr"
session.state["app:maintenance_mode"] = False
session.state["temp:api_response"] = {"data": [...]}
```

### Referencing State in Instructions

```python
agent = LlmAgent(
    name="greeter",
    model="gemini-2.5-flash",
    instruction="""Your preferred language is {user:preferred_language}.
    Current step: {current_step}.
    Optional: {optional_value?}""",   # ? = no error if missing
)
```

### Session Services

| Service | Persistence | Use Case |
|---|---|---|
| `InMemorySessionService` | None | Development |
| `DatabaseSessionService` | SQL database | Production |
| `VertexAiSessionService` | Google Cloud | Agent Engine |

### Safe State Updates

Use context objects in tools — never modify session state directly:

```python
def my_tool(context: ToolContext, query: str) -> dict:
    context.state["search_count"] = context.state.get("search_count", 0) + 1
    return {"result": "data"}
```

Or use `output_key` to auto-save agent output:

```python
agent = LlmAgent(
    name="researcher",
    instruction="Research the topic.",
    output_key="research_results",
)
```

---

## 6. Callbacks

### Six Hook Points (Execution Order)

```python
def before_agent_callback(context: CallbackContext) -> Content | None:
    """Before agent starts. Return Content to skip agent entirely."""
    return None

def before_model_callback(context: CallbackContext, request: LlmRequest) -> LlmResponse | None:
    """Before LLM call. Return LlmResponse to skip the LLM."""
    return None

def before_tool_callback(context: ToolContext, tool, args: dict) -> dict | None:
    """Before tool runs. Return dict to skip tool execution."""
    if tool.name == "delete_user" and not context.state.get("user:is_admin"):
        return {"status": "error", "error": "Unauthorized"}
    return None

def after_tool_callback(context: ToolContext, tool, args: dict, result: dict) -> dict:
    """After tool runs. Can modify result."""
    return result

def after_model_callback(context: CallbackContext, response: LlmResponse) -> LlmResponse:
    """After LLM responds. Can modify response."""
    return response

def after_agent_callback(context: CallbackContext) -> Content | None:
    """After agent completes."""
    return None

agent = LlmAgent(
    name="assistant",
    model="gemini-2.5-flash",
    instruction="Help users.",
    before_agent_callback=before_agent_callback,
    before_model_callback=before_model_callback,
    before_tool_callback=before_tool_callback,
    after_tool_callback=after_tool_callback,
    after_model_callback=after_model_callback,
    after_agent_callback=after_agent_callback,
)
```

### Common Callback Use Cases

```python
# Caching — skip LLM for repeated queries
def before_model_callback(context, request):
    cache_key = hash(request.contents[-1].parts[0].text)
    if cached := cache.get(cache_key):
        return cached
    return None

# PII redaction — scrub before sending to LLM
def before_model_callback(context, request):
    text = request.contents[-1].parts[0].text
    request.contents[-1].parts[0].text = redact_pii(text)
    return None

# Tool authorization
def before_tool_callback(context, tool, args):
    if tool.name == "access_database" and not is_authorized(context):
        return {"status": "error", "error": "Access denied"}
    return None
```

---

## 7. Guardrails

### In-Tool Guardrails

Separate LLM-provided arguments (untrusted) from developer policies (trusted):

```python
def query_database(query: str) -> dict:
    """Query database with safety checks.

    Args:
        query: SQL query (LLM-provided, untrusted)
    """
    query_upper = query.upper()
    if not query_upper.startswith("SELECT"):
        return {"status": "error", "error": "Only SELECT queries permitted"}

    dangerous = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER"]
    if any(kw in query_upper for kw in dangerous):
        return {"status": "error", "error": "Destructive operations not allowed"}

    return {"status": "success", "results": db.execute(query)}
```

### Safety Settings

```python
from google.genai import types

agent = LlmAgent(
    name="safe_agent",
    model="gemini-2.5-flash",
    generate_content_config=types.GenerateContentConfig(
        safety_settings=[
            types.SafetySetting(
                category="HARM_CATEGORY_HATE_SPEECH",
                threshold="BLOCK_MEDIUM_AND_ABOVE",
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT",
                threshold="BLOCK_MEDIUM_AND_ABOVE",
            ),
        ]
    ),
)
```

---

## 8. Error Handling

### Reflect and Retry Plugin

```python
from google.adk.plugins import ReflectAndRetryToolPlugin

retry_plugin = ReflectAndRetryToolPlugin(max_retries=3)
runner = InMemoryRunner(agent=root_agent, plugins=[retry_plugin])
```

How it works: tool fails → plugin intercepts → LLM reflects on error → retries with corrected arguments.

### In-Tool Retry with Backoff

```python
async def api_call(endpoint: str) -> dict:
    """Call external API with retry.

    Args:
        endpoint: API endpoint
    """
    for attempt in range(3):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(endpoint) as resp:
                    resp.raise_for_status()
                    return {"status": "success", "data": await resp.json()}
        except aiohttp.ClientError as e:
            if attempt == 2:
                return {"status": "error", "error": f"Failed after 3 attempts: {e}"}
            await asyncio.sleep(2 ** attempt)
```

---

## 9. Testing

### Unit Test with InMemoryRunner

```python
import pytest
from google.adk.runners import InMemoryRunner
from google.adk.sessions import InMemorySessionService

@pytest.mark.asyncio
async def test_weather_agent():
    session_service = InMemorySessionService()
    session = session_service.create_session(app_name="test", user_id="test_user")
    runner = InMemoryRunner(agent=weather_agent, session_service=session_service)

    response = await runner.run(session_id=session.id, user_message="Weather in London?")

    assert "London" in response.text
```

### Testing Without LLM Calls

Use `before_model_callback` to bypass the LLM:

```python
def bypass_llm(context, request):
    return LlmResponse(candidates=[{
        "content": {"parts": [{"text": "Canned response"}]}
    }])

agent = LlmAgent(
    name="test_agent",
    model="gemini-2.5-flash",
    before_model_callback=bypass_llm,
)
```

### Golden Dataset Testing

```python
GOLDEN = [
    {"input": "Weather in Paris?", "expected_tools": ["get_weather"]},
    {"input": "Book flight to Tokyo", "expected_tools": ["search_flights", "create_booking"]},
]

@pytest.mark.parametrize("case", GOLDEN)
async def test_trajectory(case):
    tool_calls = []

    def track(context, tool, args):
        tool_calls.append(tool.name)
        return None

    agent = LlmAgent(name="test", tools=[...], before_tool_callback=track)
    runner = InMemoryRunner(agent=agent, session_service=InMemorySessionService())
    session = runner.session_service.create_session("test", "user")

    await runner.run(session.id, case["input"])
    assert tool_calls == case["expected_tools"]
```

---

## 10. Structured Output

### Output Schema with Pydantic

```python
from pydantic import BaseModel, Field

class CapitalInfo(BaseModel):
    country: str = Field(description="The country name")
    capital: str = Field(description="The capital city")
    population: int = Field(description="Capital population")

agent = LlmAgent(
    name="capital_agent",
    model="gemini-2.5-flash",
    instruction="Provide capital city information.",
    output_schema=CapitalInfo,
)
```

### Tools + Output Schema (Gemini 3.0+ required)

For older models, split into two sequential agents:

```python
tool_agent = LlmAgent(
    name="data_gatherer",
    tools=[get_capital_city],
    output_key="raw_data",
)

formatter = LlmAgent(
    name="formatter",
    instruction="Format {raw_data} into structured output.",
    output_schema=CapitalInfo,
)

pipeline = SequentialAgent(name="pipeline", sub_agents=[tool_agent, formatter])
```

---

## 11. Authentication

### API Key

```python
from google.adk.auth import AuthCredential, AuthCredentialType

api_auth = AuthCredential(
    type=AuthCredentialType.API_KEY,
    api_key_header="X-API-Key",
    api_key_value=os.getenv("EXTERNAL_API_KEY"),
)
```

### OAuth 2.0

```python
oauth_auth = AuthCredential(
    type=AuthCredentialType.OAUTH2,
    client_id=os.getenv("OAUTH_CLIENT_ID"),
    client_secret=os.getenv("OAUTH_CLIENT_SECRET"),
    scopes=["read", "write"],
)
```

For Google Cloud services, use **Application Default Credentials (ADC)**.

---

## Quick Reference

| Pattern | When to Use |
|---|---|
| Single LlmAgent | Simple task, one model, few tools |
| SequentialAgent | Pipeline: step A → step B → step C |
| ParallelAgent | Independent tasks that can run concurrently |
| AgentTool | Parent explicitly invokes specialist sub-agents |
| output_key + state refs | Pass data between agents in a pipeline |
| Callbacks | Inject logic at model/tool boundaries |
| output_schema | Enforce typed JSON output |

---

---

## ADK Official Documentation Index

### Start Here

| Topic | URL |
|---|---|
| ADK Home / Overview | https://google.github.io/adk-docs/ |
| Technical Overview | https://google.github.io/adk-docs/get-started/about/ |
| Quickstart (Install & First Agent) | https://google.github.io/adk-docs/get-started/quickstart/ |

### Agents — Core Concepts

| Topic | URL |
|---|---|
| Agents Overview (LlmAgent, types) | https://google.github.io/adk-docs/agents/ |
| LLM Agents (root agents, instructions, tools) | https://google.github.io/adk-docs/agents/llm-agents/ |
| Custom Agents (BaseAgent subclassing) | https://google.github.io/adk-docs/agents/custom-agents/ |

### Multi-Agent Systems

| Topic | URL |
|---|---|
| Multi-Agent Architecture Overview | https://google.github.io/adk-docs/agents/multi-agents/ |
| Tutorial: Agent Team (root + sub-agents) | https://google.github.io/adk-docs/tutorials/agent-team/ |

### Workflow Agents

Deterministic controllers: SequentialAgent, ParallelAgent, LoopAgent — alongside LLM-driven dynamic routing.

| Topic | URL |
|---|---|
| Workflow Agents Overview | https://google.github.io/adk-docs/agents/workflow-agents/ |
| Sequential Agents | https://google.github.io/adk-docs/agents/workflow-agents/sequential-agents/ |
| Parallel Agents | https://google.github.io/adk-docs/agents/workflow-agents/parallel-agents/ |
| Loop Agents | https://google.github.io/adk-docs/agents/workflow-agents/loop-agents/ |

### Agent-to-Agent (A2A) Protocol

Build multi-agent systems with root agents, local sub-agents, and remote A2A agents.

| Topic | URL |
|---|---|
| A2A Overview | https://google.github.io/adk-docs/a2a/ |
| Introduction to A2A | https://google.github.io/adk-docs/a2a/intro/ |
| Quickstart: Consuming a Remote Agent (Python) | https://google.github.io/adk-docs/a2a/quickstart-consuming/ |
| Quickstart: Exposing Your Agent via A2A | https://google.github.io/adk-docs/a2a/quickstart-exposing/ |
| A2A Quickstart (Go) | https://google.github.io/adk-docs/a2a/quickstart-consuming-go/ |
| A2A Quickstart (Java) | https://google.github.io/adk-docs/a2a/quickstart-consuming-java/ |
| Official A2A Protocol Site | https://google.github.io/A2A/ |

### Tools

| Topic | URL |
|---|---|
| Tools Overview | https://google.github.io/adk-docs/tools/ |
| Custom Tools | https://google.github.io/adk-docs/tools-custom/ |
| Built-in Tools | https://google.github.io/adk-docs/tools/built-in-tools/ |
| MCP Tools | https://google.github.io/adk-docs/tools/mcp-tools/ |
| Agents as Tools | https://google.github.io/adk-docs/tools/agent-as-tools/ |
| Tools & Integrations Directory | https://google.github.io/adk-docs/integrations/ |

### Sessions, State & Memory

| Topic | URL |
|---|---|
| Sessions, State & Memory Overview | https://google.github.io/adk-docs/sessions/ |
| Session Management | https://google.github.io/adk-docs/sessions/session/ |
| State Management | https://google.github.io/adk-docs/sessions/state/ |
| Memory (Long-Term Knowledge) | https://google.github.io/adk-docs/sessions/memory/ |
| Context (InvocationContext) | https://google.github.io/adk-docs/context/ |

### Callbacks & Plugins

Hook into execution at specific points — before/after model calls, before/after tool use — for guardrails, logging, or behavior modification.

| Topic | URL |
|---|---|
| Callbacks Overview | https://google.github.io/adk-docs/callbacks/ |
| Types of Callbacks | https://google.github.io/adk-docs/callbacks/types-of-callbacks/ |
| Callback Design Patterns | https://google.github.io/adk-docs/callbacks/design-patterns-and-best-practices/ |
| Plugins | https://google.github.io/adk-docs/plugins/ |

### Deployment, Evaluation & Debugging

| Topic | URL |
|---|---|
| Evaluation | https://google.github.io/adk-docs/evaluate/ |
| Deployment Overview | https://google.github.io/adk-docs/deploy/ |
| Deploy to Cloud Run | https://google.github.io/adk-docs/deploy/cloud-run/ |
| Deploy to Agent Engine (Vertex AI) | https://google.github.io/adk-docs/deploy/agent-engine/ |
| CLI & Dev UI (local testing) | https://google.github.io/adk-docs/runtime/ |
| Apps (Runner & workflow management) | https://google.github.io/adk-docs/apps/ |

### Models & API Reference

| Topic | URL |
|---|---|
| Models Overview (Gemini, third-party) | https://google.github.io/adk-docs/models/ |
| Python API Reference | https://google.github.io/adk-docs/api-reference/python/google-adk.html |
| Coding with AI Guide | https://google.github.io/adk-docs/coding-with-ai/ |
| Community Resources | https://google.github.io/adk-docs/community/ |

### Key Pages for Building Agent-Builder Agents

| Topic | Why It Matters |
|---|---|
| [Multi-Agent Architecture](https://google.github.io/adk-docs/agents/multi-agents/) | Structure root + sub-agents |
| [Agent Team Tutorial](https://google.github.io/adk-docs/tutorials/agent-team/) | Delegation patterns walkthrough |
| [Custom Agents](https://google.github.io/adk-docs/agents/custom-agents/) | Subclass BaseAgent for dynamic behavior |
| [Sessions & State](https://google.github.io/adk-docs/sessions/state/) | Persist data across turns |
| [A2A Intro](https://google.github.io/adk-docs/a2a/intro/) | If generated agents need to talk to each other |
| [Callbacks](https://google.github.io/adk-docs/callbacks/) | Guardrails and flow control |

---

**ADK Version**: 2.0+ · **Last Verified**: June 2026
