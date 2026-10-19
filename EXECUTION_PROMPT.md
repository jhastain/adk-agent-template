# Agent Builder Prompt

Copy everything below the line into a fresh Claude Code session to create, test, deploy, and interact with a new agent.

---

You are going to help me create a new ADK agent from the Agent-Template. This is a gated workflow — pause at each gate for my confirmation before proceeding.

## Step 1: Intake

Ask me ALL of these in a single message. Suggest defaults based on my first answer:

1. **What does this agent do?** (one sentence)
2. **Agent name** — suggest a PascalCase name with `-Agent` suffix (e.g., `DataAnalyzer-Agent`). I'll confirm or change.
3. **What local tools does it need?** (Python functions — e.g., "calculate estimates", "parse CSV files")
4. **What MCP tools from the gateway?** Ask the user which servers their gateway exposes. An
   example roster:
   - `azure_devops` - repos, PRs, branches, work items, code search
   - `atlassian` - Jira issues, Confluence pages
   - `datadog` - monitors, dashboards, metrics
   - `sentry` - error tracking, issues
   - `context7` - library documentation lookup

   List which servers and/or specific tools. Say "none" if not needed.
5. **Gateway virtual key** - the agent reaches both the LLM and the MCP servers through one
   OpenAI-compatible gateway, with the same key for both. **Required.**
6. **Model preference?** Every model routes through the gateway, so any model it serves is
   available (default: `claude-sonnet-4-6`). Do NOT add a `vertex/` or `openai/` prefix - the
   template handles provider routing, and the prefix it uses is load-bearing (see Rules).
7. **Deployment group email?** (default: `platform-team@example.com`)

Show me the derived variables for confirmation before proceeding:
- `AGENT_NAME` = PascalCase-Agent (e.g., `DataAnalyzer-Agent`)
- `AGENT_NAME_LOWER` = lowercase_underscores (e.g., `data_analyzer`) **CRITICAL: must be valid Python identifier — no hyphens**
- `SERVICE_PREFIX` = lowercase, no separators (e.g., `dataanalyzer`)
- `AGENT_DISPLAY_NAME` = human-readable (e.g., `Data Analyzer Agent`)
- GCP projects: `{SERVICE_PREFIX}-dev-project`, `{SERVICE_PREFIX}-test-project`, `{SERVICE_PREFIX}-prod-project`

---

## GATE 1: Design Approval

**STOP and wait for my confirmation** after showing derived variables. Do not proceed until I say go.

---

## Step 2: Scaffold (execute without asking through step 4)

### 2.1 Create ADO Repo & Clone
```bash
az repos create --name "{AGENT_NAME}" --organization https://dev.azure.com/your-org --project YourProject -o json
git clone https://your-org@dev.azure.com/your-org/YourProject/_git/{AGENT_NAME} <your-workspace>/{AGENT_NAME}
```
If repo already exists, just clone it.

### 2.2 Copy Template
```bash
cp -r <path-to-this-template>/{ADOYaml,InfrastructureAsCode,agents,tests,bin,docs,.gitignore,.gitattributes,.pre-commit-config.yaml,.env.example,.envrc,pyproject.toml,README.md,CLAUDE.md} /c/repos/{AGENT_NAME}/
```
Do NOT copy EXECUTION_PROMPT.md or template.config.yml - they belong to the template, not to the generated repo.

### 2.3 Token Replacement

**ORDER MATTERS (longest tokens first to avoid partial matches)**:
1. `{{AGENT_DISPLAY_NAME}}` → value
2. `{{AGENT_NAME_LOWER}}` → value
3. `{{DEPLOYMENT_GROUP_EMAIL}}` → value
4. `{{SERVICE_PREFIX}}` → value
5. `{{AGENT_NAME}}` → value **(LAST — substring of AGENT_NAME_LOWER)**

Apply to all `*.py *.yml *.yaml *.toml *.sh *.md *.hcl` files in the repo.

Then rename directories:
```bash
mv "agents/{{AGENT_NAME_LOWER}}" "agents/{AGENT_NAME_LOWER value}"
mv "InfrastructureAsCode/{{SERVICE_PREFIX}}" "InfrastructureAsCode/{SERVICE_PREFIX value}"
```

Verify no leftover tokens:
```bash
grep -r '{{' . --include='*.py' --include='*.yml' --include='*.toml' --include='*.sh' --include='*.md' --include='*.hcl'
```

### 2.4 Configure Environments

The template defaults to dev/test/prod. Adjust based on the environments from intake question 8:

**If user specified fewer environments (e.g., dev + prod only):**

1. Delete unused IaC directories:
   ```bash
   rm -rf InfrastructureAsCode/{SERVICE_PREFIX}/test  # if no test
   ```

2. Remove the unused deploy stage from `ADOYaml/fullenv-pipeline.yml`:
   - Delete the entire `DeployTestStage` block (if no test)
   - Update the next stage's `dependsOn` to point to the previous stage. E.g., if removing test, change `DeployProdStage.dependsOn` from `DeployTestStage` to `DeployDevStage`

3. Remove unused IaC stages from `ADOYaml/fullenv-pipeline.yml`:
   - Remove the `wif-terragrunt-stage-template` block for the unused env
   - Remove the env from the `ENVIRONMENTS` array in `detect-iac-changes-stage-template`
   - Remove the `GCP_PROJECT_NUMBER_*` and `GCP_WIF_POOL_ID_*` variables for the unused env

4. Remove unused IaC stages from `ADOYaml/agent-pull-request.yml` — same changes as above

**If user specified custom GCP projects (not the default {PREFIX}-{env}-project):**

1. Update `agents/{name}/.env` — set `GOOGLE_CLOUD_PROJECT` to the dev project
2. Update `InfrastructureAsCode/{prefix}/{env}/project.hcl` — for each env, replace the `project_id` derivation with the actual project ID:
   ```hcl
   locals {
     project_id     = "actual-project-id-here"
     project_number = run_cmd("--terragrunt-quiet", "gcloud", "projects", "describe", local.project_id, "--format=value(projectNumber)")
   }
   ```
3. Update `ADOYaml/fullenv-pipeline.yml` — change the `GOOGLE_CLOUD_PROJECT` env vars in each deploy stage to match
4. Update `bin/deploy-agent-engine.sh` — change the `PROJECT` derivation or set `GOOGLE_CLOUD_PROJECT` env var before calling

## Step 3: Write the Agent (execute without asking)

1. **`agents/{name}/prompts.py`** — system instruction for this agent:
   - Be specific about role and capabilities
   - Do NOT use curly braces `{}` anywhere — ADK treats them as state variables
   - Include behavioral guidelines
   - Under 500 words

2. **`agents/{name}/tools.py`** — local tool functions:
   - Type hints on all parameters
   - Descriptive docstring with Args section (ADK generates schemas from these)
   - Return `str` or `dict` (with `"status"` key for dicts)
   - Write real implementations, not stubs

3. **MCP tools** (if gateway tools requested):
   - Update `agents/{name}/mcp_tools.py` — set `tool_filter` to only the needed tools
   - Set `LLM_GATEWAY_TOKEN` in `agents/{name}/.env`

4. **`agents/{name}/agent.py`** — wire in local tools + gateway toolset:
   ```python
   from .tools import my_tool
   from .mcp_tools import create_gateway_toolset

   gateway = create_gateway_toolset(tool_filter=["tool_name_1", "tool_name_2"])
   root_agent = Agent(tools=[gateway, my_tool])
   ```
   If no MCP tools, do NOT import gateway.

5. **`tests/unit/test_tools.py`** — tests for the local tools you wrote

6. **`agents/{name}/.env`** — set `GOOGLE_CLOUD_PROJECT` to the dev project from intake and `LLM_GATEWAY_TOKEN`

7. **`agents/{name}/requirements.txt`** — Agent Engine uses this (not pyproject.toml) to build its remote venv. If you added new dependencies, add them here too. The template includes the baseline deps; add any agent-specific packages.

## Step 4: Git Commit & Push

```bash
cd <your-workspace>/{AGENT_NAME}
git add -A
git commit -m "Initial scaffolding from Agent-Template"
git push -u origin main
```

If the repo has no default branch yet (empty repo), this creates `main`.

## Step 5: Test Locally

```bash
uv sync
```

Verify GCP auth: `gcloud auth application-default print-access-token`
If fails, tell me to run: `! gcloud auth application-default login`

Kill any running adk process, then start:
```bash
adk web agents/
```
Verify the agent loads without errors in the console.

---

## GATE 2: Local Verification

**STOP and tell me the agent is running locally.** Tell me to open http://localhost:8000, test it, and confirm it works before proceeding. Wait for my go.

---

## Step 6: GCP Project Setup

Check if the dev project exists:
```bash
gcloud projects describe {SERVICE_PREFIX}-dev-project --format="value(projectId)" 2>&1
```

If the project does NOT exist, tell me and present options:
- I create it (via project factory or GCP console)
- Use an existing project for dev testing (e.g., `platform-dev-project`)

If it DOES exist, proceed:

### 6.1 Enable APIs (prerequisite — must be done before IaC)
```bash
gcloud services enable aiplatform.googleapis.com --project={DEV_GCP_PROJECT}
gcloud services enable secretmanager.googleapis.com --project={DEV_GCP_PROJECT}
gcloud services enable storage.googleapis.com --project={DEV_GCP_PROJECT}
```

### 6.2 Apply IaC (creates service account, staging bucket, and secret shell)

All resources are managed via Terragrunt — do NOT create buckets or secrets via gcloud directly or it will conflict with Terraform state.

**On Linux/CI (pipeline):**
```bash
cd <your-workspace>/{AGENT_NAME}

# Service account
cd InfrastructureAsCode/{SERVICE_PREFIX}/dev/global/service_account/agent
terragrunt plan && terragrunt apply

# GCS staging bucket
cd ../../../global/gcs_staging
terragrunt plan && terragrunt apply

# Secret Manager (creates the secret shell — value populated next)
cd ../secret_manager
terragrunt plan && terragrunt apply
```

**On Windows (local dev) — Terragrunt may fail with long path errors.** If it does, create these resources via gcloud for local dev only (the pipeline on Linux will manage IaC properly):
```bash
# Create SA
gcloud iam service-accounts create agent-{SERVICE_PREFIX} \
  --display-name="Agent {AGENT_DISPLAY_NAME}" \
  --project={DEV_GCP_PROJECT}

# Create bucket
gsutil mb -p {DEV_GCP_PROJECT} -l us-central1 gs://{SERVICE_PREFIX}-dev-agent-staging

# Create secret
gcloud secrets create gateway-vk-{SERVICE_PREFIX} --project={DEV_GCP_PROJECT}
```

If terragrunt works on your Windows machine, use that instead.

### 6.3 Populate gateway key in Secret Manager
This is the only gcloud command — it sets the secret VALUE, not the secret itself (which was created by Terragrunt).
```bash
echo -n "{LLM_GATEWAY_TOKEN}" | gcloud secrets versions add gateway-vk-{SERVICE_PREFIX} \
  --data-file=- \
  --project={DEV_GCP_PROJECT}
```

## Step 7: Deploy to Dev (Agent Engine)

```bash
cd <your-workspace>/{AGENT_NAME}
bin/deploy-agent-engine.sh dev
```

**IMPORTANT:** The deploy script uses `uv run adk deploy` (not bare `adk deploy`) to ensure the project venv's ADK version is used, not the system-installed version. This avoids version mismatch errors.

This creates a new agent on first run. Capture the **agent-engine-id** from the output (the numeric ID from `projects/NUM/locations/REGION/reasoningEngines/ID`).

For all subsequent deploys, pass the ID to **update in place** (same endpoint, no stale copies):
```bash
bin/deploy-agent-engine.sh dev {AGENT_ENGINE_ID}
```

Store the agent-engine-id per environment. These go in the pipeline variables later:
```
AGENT_ENGINE_ID_DEV=<id from first dev deploy>
AGENT_ENGINE_ID_TEST=<id from first test deploy>
AGENT_ENGINE_ID_PROD=<id from first prod deploy>
```

Verify via REST API:
```bash
ACCESS_TOKEN=$(gcloud auth print-access-token)
PROJECT_NUM=$(gcloud projects describe {SERVICE_PREFIX}-dev-project --format="value(projectNumber)")
curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
  "https://us-central1-aiplatform.googleapis.com/v1beta1/projects/$PROJECT_NUM/locations/us-central1/reasoningEngines" \
  | python -c "import sys,json; [print(r['name'],r.get('displayName','')) for r in json.load(sys.stdin).get('reasoningEngines',[])]"
```

## Step 8: Test Deployed Agent

Create `scripts/test_deployed_agent.py` with REST API approach (the SDK's stream_query method is broken). Use `gcloud auth print-access-token` with `shell=True` for Windows compatibility. Handle UTF-8 encoding for emoji output.

Test it:
```bash
python scripts/test_deployed_agent.py "Hello, what can you help me with?"
```

---

## GATE 3: Dev Deployment Verified

**STOP and show me:**
- The deployed agent's resource ID and name
- The test script output
- Any errors

Wait for my confirmation before proceeding to pipeline setup.

---

## Step 9: Create ADO Pipelines

Push must be complete (Step 4) before this works.

```bash
az pipelines create \
  --name "{AGENT_NAME}-PRBuild" \
  --yml-path "ADOYaml/agent-pull-request.yml" \
  --repository "{AGENT_NAME}" \
  --repository-type tfsgit \
  --branch main \
  --folder-path "\AgentServices\agents\{AGENT_NAME}" \
  --project YourProject \
  --org https://dev.azure.com/your-org \
  --skip-first-run

az pipelines create \
  --name "{AGENT_NAME}-BuildAndDeploy" \
  --yml-path "ADOYaml/fullenv-pipeline.yml" \
  --repository "{AGENT_NAME}" \
  --repository-type tfsgit \
  --branch main \
  --folder-path "\AgentServices\agents\{AGENT_NAME}" \
  --project YourProject \
  --org https://dev.azure.com/your-org \
  --skip-first-run

az pipelines create \
  --name "{AGENT_NAME}-DevDeploy" \
  --yml-path "ADOYaml/dev-pipeline.yml" \
  --repository "{AGENT_NAME}" \
  --repository-type tfsgit \
  --branch main \
  --folder-path "\AgentServices\agents\{AGENT_NAME}" \
  --project YourProject \
  --org https://dev.azure.com/your-org \
  --skip-first-run
```

Verify: https://dev.azure.com/your-org/YourProject/_build?definitionScope=%5CAgentServices%5Cagents

## Step 10: Production Setup Checklist

Present this as a checklist — some items need GCP admin access.

### Per-Environment (test + prod):

| # | Prerequisite | Command | Who |
|---|---|---|---|
| 1 | GCP project exists | `gcloud projects describe {ENV_GCP_PROJECT}` | GCP Admin |
| 2 | APIs enabled | `gcloud services enable aiplatform.googleapis.com secretmanager.googleapis.com storage.googleapis.com --project={ENV_GCP_PROJECT}` | GCP Admin |
| 3 | IaC applied (SA + bucket + secrets) | `cd InfrastructureAsCode/{SERVICE_PREFIX}/{env}/global/{resource} && terragrunt apply` (for service_account, gcs_staging, secret_manager) | SRE |
| 4 | gateway key created | Create per-env key at https://llm-gateway.example.com | SharedPlatform |
| 5 | Key value populated | `echo -n "gw-key-..." \| gcloud secrets versions add gateway-vk-{SERVICE_PREFIX} --data-file=- --project={ENV_GCP_PROJECT}` | SRE |
| 6 | WIF setup | Follow `docs/wif-setup.md` in this template (see below) | SRE / GCP Admin |

### WIF Setup (per environment)

Follow the full guide in `docs/wif-setup.md`. Quick summary:

1. **Check if WIF pool already exists** in the target project — shared SRE projects (`platform-dev-project`, `platform-prod-project`) already have pools. For those, skip to step 4.
2. **Create WIF pool** (if needed): `{SERVICE_PREFIX}-{env}-wlif-pool`
3. **Create OIDC provider** (if new pool): `azuredevops-wlif-provider` with your Azure AD tenant ID `<AZURE_TENANT_ID>`
4. **Add SA impersonation binding**: grant `roles/iam.workloadIdentityUser` to the agent's SA from the WIF pool
5. **Update pipeline variables** with project numbers and pool names

### Pipeline Variables:

Fill in WIF project numbers and pool names in `ADOYaml/fullenv-pipeline.yml`:
```yaml
GCP_PROJECT_NUMBER_DEV: "{number}"
GCP_WIF_POOL_ID_DEV: "{pool-name}"  # e.g., sre-dev-wlif-pool (shared) or {SERVICE_PREFIX}-dev-wlif-pool (dedicated)
GCP_PROJECT_NUMBER_TEST: "{number}"
GCP_WIF_POOL_ID_TEST: "{pool-name}"
GCP_PROJECT_NUMBER_PROD: "{number}"
GCP_WIF_POOL_ID_PROD: "{pool-name}"
```
Get project numbers: `gcloud projects describe {ENV_GCP_PROJECT} --format="value(projectNumber)"`

### First Pipeline Deploy:

Commit the WIF numbers, push, and the pipeline runs:
```
merge → IaC apply → adk deploy (dev) → [manual gate] → adk deploy (test) → [manual gate] → adk deploy (prod)
```

---

## GATE 4: Production Ready

**STOP and print the full summary:**

- **Repo**: name, local path, ADO URL
- **Agent**: name, purpose, tools (local + MCP), model
- **GCP Projects**: {SERVICE_PREFIX}-dev/test/prod-project
- **Dev deployment**: resource ID, resource name
- **Local dev**: `adk web agents/` at http://localhost:8000
- **Query deployed agent**: REST API curl command and Python script path
- **Update agent**: redeploy from newer commit (rollback = redeploy older commit)
- **Delete agent**: REST API or gcloud command
- **Pipelines**: ADO folder path and URLs
- **Production status**: checklist of completed vs remaining items

---

## Rules

- **STOP at every gate.** Do not proceed past a gate without user confirmation.
- Between gates, execute without asking for confirmation.
- If a step fails, diagnose, fix, and continue to the next gate.
- If `az repos create` fails (exists), just clone.
- If `uv sync` fails, check Python version (needs 3.13+).
- Agent name in `agent.py` and directory name MUST use underscores, not hyphens.
- Do NOT use curly braces in `prompts.py`.
- Kill any running adk process before starting a new one.
- Write real, functional tool code — not placeholder stubs.
- If deployment fails (missing API, permissions), report the error clearly and stop.
- The LiteLlm model wrapper uses `openai/` prefix to bypass Agent Engine's GOOGLE_GENAI_USE_VERTEXAI injection. Do NOT change this — gateway handles provider routing server-side.
- Git commit and push MUST happen before pipeline creation.
- IaC must be applied before pipeline deploys (service accounts must exist).
- **Always use `uv run adk deploy`** — never bare `adk deploy`. The system-installed ADK version may not match the project's.
- **Set `PYTHONIOENCODING=utf-8`** before deploy commands on Windows — ADK prints emoji that break Windows console encoding.
- **`agents/{name}/requirements.txt` must stay in sync with `pyproject.toml`** — Agent Engine uses requirements.txt, not pyproject.toml, to build its remote venv.
- **On Windows, Terragrunt may fail with long path errors** — use gcloud fallback commands for local dev. The pipeline (Linux) handles IaC properly.
- GCP project naming defaults to `{SERVICE_PREFIX}-{env}-project`, but user may specify different projects in intake.
