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

# Always sync nginx config from repo and reload
NGINX_AVAILABLE=/etc/nginx/sites-available/openexchange.conf
NGINX_ENABLED=/etc/nginx/sites-enabled/openexchange
cp "$REPO_DIR/deploy/nginx.conf" "$NGINX_AVAILABLE"
ln -sf "$NGINX_AVAILABLE" "$NGINX_ENABLED"
if nginx -t; then
  systemctl reload nginx
else
  echo "nginx config test failed — not reloading" >&2
  exit 1
fi

# Ensure TLS cert exists and is current
if command -v certbot >/dev/null 2>&1; then
  if [[ -d /etc/letsencrypt/live/stock.animeshchouhan.com ]]; then
    certbot renew --quiet
  else
    certbot --nginx -d stock.animeshchouhan.com
  fi
fi
