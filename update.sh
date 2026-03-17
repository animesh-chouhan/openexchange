#!/usr/bin/env bash

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_NAME="openexchange"

cd "$REPO_DIR"

CURRENT_BRANCH="$(git branch --show-current)"

git fetch origin
git pull --ff-only origin "$CURRENT_BRANCH"
systemctl restart "${SERVICE_NAME}.service"
systemctl status "${SERVICE_NAME}.service" --no-pager
