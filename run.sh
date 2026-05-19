#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "$0")"

# Activate repository venv if present
if [[ -f ".venv/bin/activate" ]]; then
	# shellcheck disable=SC1090
	source .venv/bin/activate
fi

exec uvicorn server:app --host 0.0.0.0 --port 8000
