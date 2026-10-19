# Workload Identity Federation: Azure DevOps → GCP

The pipelines in `ADOYaml/` authenticate to GCP with **no service-account key anywhere** — not in a
variable group, not in a secure file, not in Key Vault. A pipeline mints a short-lived Entra token,
trades it for a short-lived Google access token, and uses that. This document is what you need to set
up once per environment.

Substitute your own tenant ID, project numbers and names throughout. The placeholders here are
deliberately not real values.

## How the exchange works

```
┌─ job: WifAuth<Env> ────────────────────────────────────────────┐
│  AzureCLI@2 against the federated service connection           │
│    az account get-access-token --query accessToken -o tsv      │
│  → publish as a cross-job output variable, issecret=true       │
└───────────────────────────────┬────────────────────────────────┘
                                │  Entra-issued JWT
┌─ job: Deploy<Env> ────────────▼────────────────────────────────┐
│  POST https://sts.googleapis.com/v1/token                      │
│    grant_type        = urn:ietf:params:oauth:grant-type:       │
│                        token-exchange            (RFC 8693)    │
│    subject_token     = <the Entra JWT>                         │
│    subject_token_type= ...:token-type:jwt                      │
│    requested_token_type = ...:token-type:access_token          │
│    audience = //iam.googleapis.com/projects/<PROJECT_NUMBER>   │
│               /locations/global/workloadIdentityPools/<POOL>   │
│               /providers/<PROVIDER>                            │
│  → access_token written to /tmp/gcp_token                      │
│  gcloud config set auth/access_token_file /tmp/gcp_token       │
│  bin/deploy-agent-engine.sh <env>                              │
└────────────────────────────────────────────────────────────────┘
```

Two properties worth naming:

- The Entra JWT is marked `issecret=true` when it crosses the job boundary, so it is masked in logs.
- `auth/access_token_file` rather than `gcloud auth activate-service-account` means no credential
  ever lands in gcloud's own config store, and the token expires on its own in under an hour.

## One-time setup, per environment

Variables used below:

| Name | Example | Where it comes from |
| --- | --- | --- |
| `PROJECT_ID` | `dataanalyzer-dev-project` | your GCP project |
| `PROJECT_NUMBER` | `123456789012` | `gcloud projects describe $PROJECT_ID --format='value(projectNumber)'` |
| `POOL_ID` | `agents-dev-wlif-pool` | your choice; `ADOYaml/*.yml` `GCP_WIF_POOL_ID_*` must match |
| `PROVIDER_ID` | `azuredevops-wlif-provider` | your choice; `GCP_WIF_PROVIDER_ID` must match |
| `AZURE_TENANT_ID` | `<AZURE_TENANT_ID>` | Entra → Overview → Tenant ID |
| `SA_EMAIL` | `agent-dataanalyzer@dataanalyzer-dev-project.iam.gserviceaccount.com` | created by the Terragrunt `service_account/agent` module |

### 1. Enable the APIs

```bash
gcloud services enable iamcredentials.googleapis.com sts.googleapis.com \
  --project="$PROJECT_ID"
```

### 2. Create the pool (once per environment)

```bash
gcloud iam workload-identity-pools create "$POOL_ID" \
  --project="$PROJECT_ID" \
  --location="global" \
  --display-name="Azure DevOps pipelines ($ENV)"
```

A pool can be shared across several agents in the same project. The template's
`fullenv-pipeline.yml` uses a per-agent pool (`{{SERVICE_PREFIX}}-{env}-wlif-pool`) while
`agent-pull-request.yml` uses a shared one (`agents-{env}-wlif-pool`) — pick one convention and make
both files agree.

### 3. Create the OIDC provider

```bash
gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
  --project="$PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="$POOL_ID" \
  --issuer-uri="https://login.microsoftonline.com/${AZURE_TENANT_ID}/v2.0" \
  --allowed-audiences="api://AzureADTokenExchange" \
  --attribute-mapping="google.subject=assertion.sub"
```

The issuer URI carries your Entra tenant ID, which is why that value is environment-specific and is
a placeholder in this repo.

### 4. Bind the pipeline identity to the agent service account

```bash
gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --project="$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principal://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/subject/${APP_OBJECT_ID}"
```

`APP_OBJECT_ID` is the object ID of the Entra app registration behind the Azure DevOps service
connection. Use `principalSet://.../attribute.<name>/<value>` instead if you mapped an attribute
rather than the subject.

### 5. Create the Azure DevOps service connection

In Azure DevOps → Project settings → Service connections, create an **Azure Resource Manager**
connection using **Workload Identity federation (automatic)**. Name it to match the
`azureSubscription:` value in the pipelines — `ADO-GCP-WIF` in this template.

### 6. Fill in the pipeline variables

`ADOYaml/*.yml` ship with `"TBD"` placeholders on purpose:

```yaml
GCP_PROJECT_NUMBER_DEV:  "TBD"   # from step 2's variables table
GCP_WIF_POOL_ID_DEV:     "agents-dev-wlif-pool"
GCP_WIF_PROVIDER_ID:     "azuredevops-wlif-provider"
AGENT_ENGINE_ID_DEV:     "TBD"   # after the first deploy
```

Project numbers come from step 2. Agent engine IDs do not exist until the first deploy has run — see
the README on why they matter (without them, every deploy creates a duplicate engine).

## What the service account is allowed to do

The Terragrunt `service_account/agent` module grants exactly five roles, all scoped to the agent's
own project:

| Role | Why |
| --- | --- |
| `roles/aiplatform.user` | create and invoke the Agent Engine reasoning engine |
| `roles/logging.logWriter` | write runtime logs |
| `roles/monitoring.metricWriter` | write runtime metrics |
| `roles/secretmanager.secretAccessor` | read the gateway key at startup |
| `roles/serviceusage.serviceUsageConsumer` | call enabled services |

Note the `agent-` name prefix: GCP service-account names must be 6–30 characters, and a short agent
name alone would fail validation.

## Verifying before you run a pipeline

```bash
# Does the provider exist and point at the right issuer?
gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" \
  --project="$PROJECT_ID" --location=global --workload-identity-pool="$POOL_ID"

# Can the binding be seen on the service account?
gcloud iam service-accounts get-iam-policy "$SA_EMAIL" --project="$PROJECT_ID"
```

A failed exchange returns HTTP 400 with an `error_description` that names the mismatched field —
audience, issuer or subject. Read it; it is specific.

## Common failures

| Symptom | Cause |
| --- | --- |
| `Invalid value for "audience"` | The `audience` in the pipeline does not byte-match the provider resource path. Check the project **number**, not the project ID. |
| `The given credential is rejected by the attribute condition` | Your attribute mapping or condition does not match the Entra token's claims. |
| `Permission 'iam.serviceAccounts.getAccessToken' denied` | Step 4's `workloadIdentityUser` binding is missing or names the wrong principal. |
| gcloud works, deploy fails on a different project | The agent service account only has roles in its own project. Cross-project reads need an explicit grant. |
| `access_token_file` ignored | An older gcloud. The pipelines assume a version that supports it. |
