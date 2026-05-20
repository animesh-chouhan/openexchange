#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$REPO_DIR/.venv"
PYTHON="${PYTHON:-python3}"
DEPLOY_DIR="$REPO_DIR/deploy"

cd "$REPO_DIR"

echo "Using python=$PYTHON venv=$VENV_DIR deploy_dir=$DEPLOY_DIR"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "Error: $PYTHON not found on PATH." >&2
  exit 2
fi

echo "Checking Python version..."
PYVER=$("$PYTHON" -c 'import sys; print("%d.%d" % sys.version_info[:2])')
echo "Python version: $PYVER"

if [[ -d "$VENV_DIR" ]]; then
  echo "Virtualenv already exists at $VENV_DIR. Reusing it."
else
  echo "Creating virtualenv in $VENV_DIR"
  "$PYTHON" -m venv "$VENV_DIR"
fi

echo "Activating virtualenv"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "Upgrading pip, setuptools, wheel"
pip install --upgrade pip setuptools wheel

if [[ -f requirements.txt ]]; then
  echo "Installing from requirements.txt"
  pip install -r requirements.txt
fi

if [[ -f requirements-dev.txt ]]; then
  echo "Installing developer requirements from requirements-dev.txt"
  pip install -r requirements-dev.txt
fi

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
  $SUDO ufw --force enable || true
  $SUDO ufw status verbose || true
else
  echo "ufw not available; skipped firewall configuration." >&2
fi

echo "Setup complete."
echo "Run locally with: ./scripts/run.sh"
