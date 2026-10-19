#!/usr/bin/env bash
set -o errexit -o nounset -o pipefail

ENV="${1:?Usage: deploy-agent-engine.sh <env> [agent-engine-id]}"
AGENT_ENGINE_ID="${2:-}"
PROJECT="${GOOGLE_CLOUD_PROJECT:-{{SERVICE_PREFIX}}-${ENV}-project}"
REGION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
DISPLAY_NAME="{{AGENT_DISPLAY_NAME}}"

EXTRA_ARGS=""
if [[ -n "${AGENT_ENGINE_ID}" ]]; then
    EXTRA_ARGS="--agent_engine_id=${AGENT_ENGINE_ID}"
    echo "Updating existing agent ${AGENT_ENGINE_ID} in ${PROJECT} (${REGION})..."
else
    echo "Creating new agent in ${PROJECT} (${REGION})..."
    echo "TIP: Pass the agent-engine-id as 2nd arg to update instead of create."
fi

export PYTHONIOENCODING=utf-8

cd "$(dirname "$0")/../agents"
uv run adk deploy agent_engine \
    --project="${PROJECT}" \
    --region="${REGION}" \
    --display_name="${DISPLAY_NAME}" \
    ${EXTRA_ARGS} \
    "{{AGENT_NAME_LOWER}}"
