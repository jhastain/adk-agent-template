#!/usr/bin/env bash
set -o errexit -o nounset -o pipefail
uv run ruff check .
uv run ruff format --check .
