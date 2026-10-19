# {{AGENT_NAME}}

{{AGENT_DISPLAY_NAME}} — a [Google ADK](https://google.github.io/adk-docs/) agent service deployed
to Vertex AI Agent Engine.

> **This repository is the template, not an agent.** It is a stamp you press to produce a new agent
> service repo: application skeleton, Terragrunt IaC, three Azure DevOps pipelines, test harness, and
> an LLM-driven generation prompt that walks the whole thing end to end. Every double-brace token below is
> substituted at generation time.
>
> Portfolio copy of a template I built at work. Employer identifiers, project IDs, hostnames, the
> Azure tenant ID and the internal Terraform module sources have been replaced with neutral
> placeholders, and one live gateway key was removed. The architecture and every pipeline are intact.

## What is actually interesting here

**1. The scaffolder is an LLM session, and the prompt is the program.**
[`EXECUTION_PROMPT.md`](EXECUTION_PROMPT.md) is 430 lines pasted into a fresh Claude Code session:
ten steps punctuated by **four hard gates** where the session stops dead and a human verifies
something a machine cannot — does the agent actually behave correctly, did it really deploy. Between
gates the session runs freely. Its closing `Rules` block is 18 accumulated constraints, each one a
real failure that happened once.

**2. Token substitution order is load-bearing.** `{{AGENT_NAME}}` is a strict substring of
`{{AGENT_NAME_LOWER}}` and `{{AGENT_DISPLAY_NAME}}`. Replace it first and you corrupt the other two
into `value_LOWER}}`. The prescribed order — DISPLAY_NAME → NAME_LOWER → DEPLOYMENT_GROUP_EMAIL →
SERVICE_PREFIX → **NAME last** — is in [`template.config.yml`](template.config.yml), and generation
ends with `grep -r '{{'` to prove nothing survived.

**3. A non-Google model still deploys to a Google-opinionated runtime.**
`agents/{{AGENT_NAME_LOWER}}/agent.py` wraps the model in ADK's `LiteLlm` as
`model=f"openai/{model_id}"` against an OpenAI-compatible gateway. The `openai/` prefix is not
cosmetic: it deliberately bypasses Agent Engine's automatic `GOOGLE_GENAI_USE_VERTEXAI` injection,
which would otherwise force Vertex-native routing and break the gateway path. The gateway then does
provider routing server-side, so the model choice survives deployment.

**4. The directory tree *is* the IaC configuration.** Every level of
[`InfrastructureAsCode/`](InfrastructureAsCode/) derives its own identity from its own directory
name — `app_id = basename(...)`, `environment = basename(...)`, region short-forms computed from the
region directory. Rename a directory, rename the resources. The remote state path comes from
`path_relative_to_include()`, so each leaf module gets its own state file automatically.

**5. No service-account keys anywhere.** Pipelines mint an OIDC JWT from a federated service
connection, exchange it at `sts.googleapis.com` via RFC 8693 token exchange against a Workload
Identity pool, write the result to a file, and hand it to gcloud with `auth/access_token_file`.
See [`docs/wif-setup.md`](docs/wif-setup.md).

## Tokens

| Token | Meaning | Example |
| --- | --- | --- |
| `{{AGENT_NAME}}` | Repo name, PascalCase, ends `-Agent` | `DataAnalyzer-Agent` |
| `{{AGENT_NAME_LOWER}}` | ADK agent name; **must be a valid Python identifier** | `data_analyzer` |
| `{{SERVICE_PREFIX}}` | IaC `app_id` and GCP resource prefix; no separators | `dataanalyzer` |
| `{{AGENT_DISPLAY_NAME}}` | Agent Engine display name | `Data Analyzer Agent` |
| `{{DEPLOYMENT_GROUP_EMAIL}}` | Manual-gate notification target | `platform-team@example.com` |

Derived rather than tokenised: service account `agent-<prefix>@<prefix>-{env}-project`, GCP projects
`<prefix>-{dev,test,prod}-project`, staging bucket `<prefix>-{env}-agent-staging`, state bucket
`<prefix>-{env}-tfstate-us`.

## Layout

```
agents/{{AGENT_NAME_LOWER}}/   the ADK agent package (agent, config, prompts, tools, mcp_tools)
ADOYaml/                       three pipelines: PR gate, fast dev deploy, full promotion
InfrastructureAsCode/          Terragrunt: service account, staging bucket, secret shell
bin/                           one script per tool, so local and CI run the same command
tests/unit/                    always runs, no cloud
tests/integration/             opt-in, needs GCP
docs/                          ADK patterns, WIF setup, architecture diagrams
EXECUTION_PROMPT.md            the generation program
template.config.yml            token definitions and substitution order
```

## Quick start (working on an agent generated from this template)

```bash
uv sync --frozen
cp .env.example .env            # fill in your project and gateway values
adk web agents/                 # interactive UI at http://localhost:8000
uv run pytest tests/unit
python bin/e2e.py               # see Verifying
```

Prerequisites: Python 3.13+, [uv](https://docs.astral.sh/uv/),
[gcloud](https://cloud.google.com/sdk/docs/install), and
`gcloud auth application-default login`.

## Generating a new agent

Paste [`EXECUTION_PROMPT.md`](EXECUTION_PROMPT.md) into a fresh Claude Code session and answer the
seven intake questions. It handles repo creation, token substitution, directory renames, agent code,
local verification, GCP setup, the first dev deploy, and pipeline creation — stopping at each gate.

Manually, if you prefer: create the repo, copy everything except `EXECUTION_PROMPT.md` and
`template.config.yml`, substitute the tokens **longest first**, rename
`agents/{{AGENT_NAME_LOWER}}/` and `InfrastructureAsCode/{{SERVICE_PREFIX}}/`, then `grep -r '{{'`
to confirm nothing is left.

## Verifying

```bash
python bin/e2e.py
```

One command. Checks the template's own invariants — that the token set in `template.config.yml`
matches what the tree actually contains, that the documented substitution order is safe against the
substring trap, that the agent package satisfies the ADK contract, that `requirements.txt` and
`pyproject.toml` agree, that no `.env` is tracked, and that every file the pipelines and docs
reference actually exists. Anything needing GCP, Azure DevOps or a live gateway prints an explicit
`SKIP` with the reason. Non-zero exit on any failure.

## Pipelines

| File | Trigger | Does |
| --- | --- | --- |
| `ADOYaml/agent-pull-request.yml` | PR to `main` | ruff, pyright, pytest + coverage, then `terragrunt plan` **only for the modules the PR touched**, per environment |
| `ADOYaml/dev-pipeline.yml` | manual | WIF auth → deploy to dev. The fast path. |
| `ADOYaml/fullenv-pipeline.yml` | push to `main` | IaC apply dev→test→prod, then deploy dev → **[gate]** → test → **[gate]** → prod, with deployment event markers around prod |

Two pipelines consume shared stage templates from external repository resources
(`detect-iac-changes-stage-template.yml`, `wif-terragrunt-stage-template.yml`, a deployment-marker
template). **Those templates are not in this repo** — they lived in an organisation-shared repo, so
the pipelines will not run as-is. The stage wiring shows exactly what they must accept.

## Deployment

`adk deploy agent_engine` — no Docker, no registry. ADK ships the source and Agent Engine builds the
remote venv from `requirements.txt`, which is why `requirements.txt` and `pyproject.toml` have to be
kept in sync by hand.

Agent Engine has no native versioning: without `--agent_engine_id` every deploy **creates a
duplicate** rather than updating in place. Hence `AGENT_ENGINE_ID_{DEV,TEST,PROD}` as pipeline
variables, and **rollback = rerun the pipeline on an older commit**.

`bin/deploy-agent-engine.sh` is 27 lines encoding four hard-won decisions: always `uv run adk`
(never bare `adk` — the build image's ADK can differ from the project pin), pass `--agent_engine_id`
for updates, `export PYTHONIOENCODING=utf-8` (ADK prints emoji; the Windows console codepage
crashes on them), and `cd agents/` before passing the bare module name.

## Quality gates

- `pyproject.toml` sets `filterwarnings = ["error", ...]` — **warnings are failures**, with two
  named exemptions. `asyncio_mode = "strict"`.
- Ruff selects bugbear, SIM, ASYNC, bandit (`S`), no-print (`T20`) and LOG. Per-file ignores are
  confined to `tests/**`.
- Pyright runs `basic` overall but **`strict = ["agents"]`** — shipped agent code is strictly typed,
  tests are not.
- `.pre-commit-config.yaml` pins uv-lock, ruff, pyright and the standard `pre-commit-hooks` set, including
  `detect-private-key` and `check-added-large-files --maxkb=100` (16 hooks total).

## Things to change for your environment

The template is deliberately explicit about the parts that were organisation-specific:

| Where | What to replace |
| --- | --- |
| `InfrastructureAsCode/*/global/{gcs_staging,secret_manager}/terragrunt.hcl` | `<your-module-registry>/…` — these were private library modules. The inputs show what yours must accept. |
| `ADOYaml/*.yml` | the org and project in the repository resources, agent pool names (`terraform-builds`, `node-builds`), the service connection (`ADO-GCP-WIF`), and the WIF pool and provider IDs |
| `ADOYaml/*.yml` | `GCP_PROJECT_NUMBER_*` and `AGENT_ENGINE_ID_*` are `"TBD"` by design — fill them after the first apply and first deploy |
| `.env.example`, `agents/*/config.py` | gateway URLs (`llm-gateway.example.com`) |
| `docs/wif-setup.md` | your Azure tenant ID and GCP project numbers |

## Docs

| Doc | Purpose |
| --- | --- |
| [`docs/adk-patterns.md`](docs/adk-patterns.md) | ADK reference: naming rules, tool definition, multi-agent patterns, session state, callbacks, testing, structured output, auth |
| [`docs/wif-setup.md`](docs/wif-setup.md) | Workload Identity Federation: pool, provider, bindings, and the token exchange the pipelines perform |
| [`docs/adk-agent-template.drawio`](docs/adk-agent-template.drawio) | Components, generation flow and trust boundaries |
| [`docs/reference-architecture.html`](docs/reference-architecture.html) | Standalone architecture deck |
| [`docs/agent-deployment-models.html`](docs/agent-deployment-models.html) | Deployment-model comparison deck |

## License

MIT — see [LICENSE](LICENSE).
