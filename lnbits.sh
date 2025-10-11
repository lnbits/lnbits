#!/usr/bin/env bash
set -euo pipefail

# --- Config you might tweak ---
REPO_URL="https://github.com/lnbits/lnbits.git"
BRANCH="main"
APP_DIR="${PWD}/lnbits"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-5000}"
ADMIN_UI="${LNBITS_ADMIN_UI:-true}"
# -------------------------------

export DEBIAN_FRONTEND=noninteractive

# Ensure basic tooling
if ! command -v curl >/dev/null 2>&1 || ! command -v git >/dev/null 2>&1; then
  sudo apt-get update -y
  sudo apt-get install -y curl git
fi

# System build deps and secp headers
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update -y
  sudo apt-get install -y \
    pkg-config \
    build-essential \
    libsecp256k1-dev \
    automake \
    autoconf \
    libtool \
    m4
fi

# Install uv (if missing)
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
# Ensure PATH for current session
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
  export PATH="$HOME/.local/bin:$PATH"
fi

# Clone or reuse repo
if [[ ! -d "$APP_DIR/.git" ]]; then
  git clone "$REPO_URL" "$APP_DIR"
fi

cd "$APP_DIR"
git fetch --all --prune
git checkout "$BRANCH"
git pull --ff-only || true

# First-run setup
mkdir -p data
[[ -f .env ]] || cp .env.example .env || true

# Prefer system libsecp256k1 (avoid autotools path)
export SECP_BUNDLED=0

# Sync dependencies with Python 3.12
uv sync --python 3.12 --all-extras --no-dev

# Environment
export LNBITS_ADMIN_UI="$ADMIN_UI"
export HOST="$HOST"
export PORT="$PORT"

# Open firewall (optional)
if command -v ufw >/dev/null 2>&1; then
  sudo ufw allow "$PORT"/tcp || true
fi

# Run LNbits with Python 3.12 via uv
exec uv run --python 3.12 lnbits
