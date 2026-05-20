#!/usr/bin/env bash
set -euo pipefail

# When run under sudo, $HOME becomes /root and ~/.local/bin is stripped from PATH.
# Re-add the invoking user's local bin so uv is findable.
[[ -n "${SUDO_USER:-}" ]] && export PATH="/home/${SUDO_USER}/.local/bin:${PATH}"
export PATH="${HOME}/.local/bin:${PATH}"

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEPLOY_DIR="$REPO_DIR/deploy"

cd "$REPO_DIR"

# Install uv if not present
if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found — installing..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

echo "uv $(uv --version)"
echo "Syncing dependencies (uv will install Python 3.14 if needed)..."
uv sync --all-groups

SUDO=""
if [[ $EUID -ne 0 ]]; then
  SUDO="sudo"
fi

if [[ -f "$DEPLOY_DIR/nginx.conf" ]]; then
  echo "Found deploy/nginx.conf, installing nginx config"
  if command -v apt-get >/dev/null 2>&1; then
    $SUDO apt-get update
    $SUDO apt-get install -y nginx
  elif command -v dnf >/dev/null 2>&1; then
    $SUDO dnf install -y nginx
  elif command -v yum >/dev/null 2>&1; then
    $SUDO yum install -y nginx
  else
    echo "No supported package manager found for nginx. Skipping install." >&2
  fi

  TARGET_AVAILABLE=/etc/nginx/sites-available
  TARGET_ENABLED=/etc/nginx/sites-enabled
  $SUDO mkdir -p "$TARGET_AVAILABLE" "$TARGET_ENABLED"
  $SUDO cp "$DEPLOY_DIR/nginx.conf" "$TARGET_AVAILABLE/openexchange.conf"
  $SUDO ln -sf "$TARGET_AVAILABLE/openexchange.conf" "$TARGET_ENABLED/openexchange.conf"
  $SUDO ln -sf "$TARGET_AVAILABLE/openexchange.conf" "$TARGET_ENABLED/openexchange"

  echo "Testing nginx configuration"
  if $SUDO nginx -t; then
    $SUDO systemctl reload nginx || $SUDO systemctl restart nginx || true
  else
    echo "nginx configuration test failed. Leaving current nginx state unchanged." >&2
  fi
fi

if [[ -f "$DEPLOY_DIR/openexchange.service" ]]; then
  echo "Installing systemd service"
  $SUDO cp "$DEPLOY_DIR/openexchange.service" /etc/systemd/system/openexchange.service
  $SUDO systemctl daemon-reload
  $SUDO systemctl enable openexchange.service
  $SUDO systemctl restart openexchange.service || $SUDO systemctl start openexchange.service || true
fi

echo "Configuring UFW if available"
if ! command -v ufw >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    $SUDO apt-get update
    $SUDO apt-get install -y ufw
  elif command -v dnf >/dev/null 2>&1; then
    $SUDO dnf install -y ufw || true
  elif command -v yum >/dev/null 2>&1; then
    $SUDO yum install -y ufw || true
  fi
fi

if command -v ufw >/dev/null 2>&1; then
  $SUDO ufw allow OpenSSH || $SUDO ufw allow 22/tcp || true
  $SUDO ufw allow 80/tcp || true
  $SUDO ufw allow 443/tcp || true
  $SUDO ufw allow 8000/tcp || true
  $SUDO ufw allow 9090/tcp || true
  $SUDO ufw allow 3000/tcp || true
  $SUDO ufw --force enable || true
  $SUDO ufw status verbose || true
else
  echo "ufw not available; skipped firewall configuration." >&2
fi

echo "Setup complete."
echo "Run locally with: ./scripts/run.sh"
