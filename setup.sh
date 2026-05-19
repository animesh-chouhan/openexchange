#!/usr/bin/env bash
set -euo pipefail

VENV_DIR=.venv
PYTHON=python3
FORCE=0
INSTALL_NGINX=0
#!/usr/bin/env bash
set -euo pipefail

# This script uses sensible defaults and performs a non-interactive setup:
# - Python: `python3`
# - Virtualenv: `.venv` in repo root
# - Installs `requirements.txt` and `requirements-dev.txt` if present
# - Installs and configures nginx if `server/nginx.conf` exists
# - Installs and enables systemd service if `server/openexchange.service` exists
# - Installs and enables UFW, allows OpenSSH, HTTP/HTTPS, and port 8000

VENV_DIR=.venv
PYTHON=python3
SERVER_DIR=server

echo "Using defaults: python=$PYTHON venv=$VENV_DIR server_dir=$SERVER_DIR"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "Error: $PYTHON not found on PATH." >&2
  exit 2
fi

echo "Checking Python version..."
PYVER=$($PYTHON -c 'import sys; print("%d.%d" % sys.version_info[:2])')
echo "Python version: $PYVER"

if [[ -d "$VENV_DIR" ]]; then
  echo "Virtualenv already exists at $VENV_DIR. Reusing it."
else
  echo "Creating virtualenv in $VENV_DIR"
  "$PYTHON" -m venv "$VENV_DIR"
fi

echo "Activating virtualenv"
# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

echo "Upgrading pip, setuptools, wheel"
pip install --upgrade pip setuptools wheel

if [[ -f requirements.txt ]]; then
  echo "Installing from requirements.txt"
  pip install -r requirements.txt
else
  echo "No requirements.txt found in repository root."
fi

if [[ -f requirements-dev.txt ]]; then
  echo "Installing developer requirements from requirements-dev.txt"
  pip install -r requirements-dev.txt
fi

SUDO=""
if [[ $EUID -ne 0 ]]; then
  SUDO="sudo"
fi

# Install and configure nginx if nginx config exists in server/
if [[ -f "$SERVER_DIR/nginx.conf" ]]; then
  echo "Found $SERVER_DIR/nginx.conf — installing and configuring nginx"
  if command -v apt-get >/dev/null 2>&1; then
    $SUDO apt-get update
    $SUDO apt-get install -y nginx
  elif command -v dnf >/dev/null 2>&1; then
    $SUDO dnf install -y nginx
  elif command -v yum >/dev/null 2>&1; then
    $SUDO yum install -y nginx
  else
    echo "No supported package manager found (apt/dnf/yum). Skipping nginx install." >&2
  fi

  TARGET_AVAILABLE=/etc/nginx/sites-available
  TARGET_ENABLED=/etc/nginx/sites-enabled
  $SUDO mkdir -p "$TARGET_AVAILABLE" "$TARGET_ENABLED"
  $SUDO cp "$SERVER_DIR/nginx.conf" "$TARGET_AVAILABLE/openexchange.conf"
  $SUDO ln -sf "$TARGET_AVAILABLE/openexchange.conf" "$TARGET_ENABLED/openexchange.conf"
  echo "Testing nginx configuration"
  if $SUDO nginx -t; then
    echo "Reloading nginx"
    $SUDO systemctl reload nginx || $SUDO systemctl restart nginx || true
  else
    echo "nginx configuration test failed. Leaving current nginx state unchanged." >&2
  fi
fi

# Install and enable systemd service if present
if [[ -f "$SERVER_DIR/openexchange.service" ]]; then
  echo "Found $SERVER_DIR/openexchange.service — installing systemd service"
  $SUDO cp "$SERVER_DIR/openexchange.service" /etc/systemd/system/openexchange.service
  $SUDO systemctl daemon-reload
  $SUDO systemctl enable openexchange.service
  $SUDO systemctl restart openexchange.service || $SUDO systemctl start openexchange.service || true
  echo "Systemd service installed and started/enabled."
fi

# Install and configure UFW (allow OpenSSH, HTTP/HTTPS, and 8000)
echo "Configuring UFW (if available) — will allow OpenSSH, HTTP/HTTPS, and port 8000"
if ! command -v ufw >/dev/null 2>&1; then
  echo "ufw not found — attempting to install"
  if command -v apt-get >/dev/null 2>&1; then
    $SUDO apt-get update
    $SUDO apt-get install -y ufw
  elif command -v dnf >/dev/null 2>&1; then
    $SUDO dnf install -y ufw || true
  elif command -v yum >/dev/null 2>&1; then
    $SUDO yum install -y ufw || true
  else
    echo "No supported package manager found to install ufw. Skipping ufw setup." >&2
  fi
fi

if command -v ufw >/dev/null 2>&1; then
  echo "Allowing OpenSSH to avoid lockout"
  $SUDO ufw allow OpenSSH || $SUDO ufw allow 22/tcp || true

  if [[ -f "$SERVER_DIR/nginx.conf" ]]; then
    echo "Allowing HTTP/HTTPS ports (80,443)"
    if $SUDO ufw app list 2>/dev/null | grep -q "Nginx Full"; then
      $SUDO ufw allow 'Nginx Full' || true
    else
      $SUDO ufw allow 80/tcp || true
      $SUDO ufw allow 443/tcp || true
    fi
  fi

  echo "Allowing application port 8000/tcp"
  $SUDO ufw allow 8000/tcp || true

  echo "Enabling UFW"
  $SUDO ufw --force enable || true
  echo "UFW status:"
  $SUDO ufw status verbose || true
else
  echo "ufw not available; skipped UFW configuration." >&2
fi

echo "Setup complete. To activate the venv run:"
echo "  source $VENV_DIR/bin/activate"

echo "You can run the server with the activated venv, e.g.:"
echo "  python server.py"

exit 0
      $SUDO dnf install -y ufw || true
    elif command -v yum >/dev/null 2>&1; then
      $SUDO yum install -y ufw || true
    else
      echo "No supported package manager found to install ufw. Skipping ufw setup." >&2
    fi
  fi

  if command -v ufw >/dev/null 2>&1; then
    echo "Allowing OpenSSH to avoid lockout"
    $SUDO ufw allow OpenSSH || $SUDO ufw allow 22/tcp || true

    # If nginx was installed or nginx config present, allow 80/443
    if [[ $INSTALL_NGINX -eq 1 || -f "$SERVER_DIR/nginx.conf" ]]; then
      echo "Allowing HTTP/HTTPS ports (80,443)"
      # prefer application profiles when available
      if $SUDO ufw app list 2>/dev/null | grep -q "Nginx Full"; then
        $SUDO ufw allow 'Nginx Full' || true
      else
        $SUDO ufw allow 80/tcp || true
        $SUDO ufw allow 443/tcp || true
      fi
    fi

    for p in "${ALLOW_PORTS[@]}"; do
      echo "Allowing port $p/tcp"
      $SUDO ufw allow "$p"/tcp || true
    done

    echo "Enabling UFW"
    $SUDO ufw --force enable || true
    echo "UFW status:" 
    $SUDO ufw status verbose || true
  else
    echo "ufw not available; skipped UFW configuration." >&2
  fi
fi

echo "Setup complete. To activate the venv run:"
echo "  source $VENV_DIR/bin/activate"

echo "You can run the server with the activated venv, e.g.:"
echo "  python server.py"

exit 0
