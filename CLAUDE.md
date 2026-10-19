# {{AGENT_NAME}} — Claude Code Context

## What This Is

An ADK (Google Agent Development Kit) agent service. Deploys to Google Agent Engine via ADO pipelines.

## Key Files

| File | Purpose |
|---|---|
| `agents/{{AGENT_NAME_LOWER}}/agent.py` | Agent definition — `root_agent` variable is mandatory for ADK |
| `agents/{{AGENT_NAME_LOWER}}/tools.py` | Tool functions the agent can call |
| `agents/{{AGENT_NAME_LOWER}}/prompts.py` | System instruction strings |
| `agents/{{AGENT_NAME_LOWER}}/config.py` | Settings via env vars (dataclass pattern) |
| `agents/{{AGENT_NAME_LOWER}}/mcp_tools.py` | gateway MCP gateway integration (create_gateway_toolset) |
| `agents/{{AGENT_NAME_LOWER}}/.env` | Vertex AI config + gateway API token |
| `ADOYaml/fullenv-pipeline.yml` | Main build+deploy pipeline |
| `ADOYaml/agent-pull-request.yml` | PR validation pipeline |

## Naming Convention

Repos: `<AgentName>-Agent`. ADK names: underscores only (Python identifier). IaC prefix: no separators.

## Conventions

- **Python 3.13+**, managed with UV
- **Ruff** for linting/formatting, **Pyright** for type checking
- **Sentry** for error tracking
- Tests in `tests/unit/` (always run) and `tests/integration/` (requires GCP creds)
- IaC in `InfrastructureAsCode/` — Terragrunt configs for service accounts per env
- All agents share `agents-{env}-project` GCP projects
- Deploy via `adk deploy agent_engine` (no Docker/Cloud Run)
- **gateway** is the default MCP gateway for external tools (ADO, Jira, Datadog, Sentry, etc.)

## Local Dev

```bash
adk web agents/             # ADK dev server with UI
uv run pytest tests/unit    # Run unit tests
```

## Pipeline Flow

PR: lint → type check → test → IaC plan
Main: IaC apply → `adk deploy agent_engine` → manual gates between envs

## Docs

- `docs/wif-setup.md` — WIF setup for ADO pipeline auth to GCP
- `docs/adk-patterns.md` — ADK patterns (tools, multi-agent, callbacks)
- `docs/reference-architecture.html` — visual architecture diagram
