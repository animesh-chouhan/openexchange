#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "$0")/.."

exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log
