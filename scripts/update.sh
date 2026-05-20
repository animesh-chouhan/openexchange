#!/usr/bin/env bash

set -euo pipefail

# When run under sudo, $HOME becomes /root and ~/.local/bin is stripped from PATH.
# Re-add the invoking user's local bin so uv is findable.
[[ -n "${SUDO_USER:-}" ]] && export PATH="/home/${SUDO_USER}/.local/bin:${PATH}"
export PATH="${HOME}/.local/bin:${PATH}"

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_NAME="openexchange"

cd "$REPO_DIR"

CURRENT_BRANCH="$(git branch --show-current)"

git fetch origin
BEFORE="$(git rev-parse HEAD)"
git pull --ff-only origin "$CURRENT_BRANCH"
AFTER="$(git rev-parse HEAD)"

uv sync --all-groups
systemctl restart "${SERVICE_NAME}.service"
systemctl status "${SERVICE_NAME}.service" --no-pager