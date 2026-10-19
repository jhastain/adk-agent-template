#!/usr/bin/env bash
set -o errexit -o nounset -o pipefail
uv run pytest tests/unit "$@" \
    --junitxml=test-results.xml \
    --cov=agents \
    --cov-report=term-missing \
    --cov-report=xml
