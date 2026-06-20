#!/usr/bin/env bash
set -euo pipefail
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  build-essential ca-certificates curl git jq nodejs npm python3 python3-dev python3-pip \
  python3-venv rsync tmux unzip zip
if ! command -v sfw >/dev/null 2>&1; then
  sudo npm install -g sfw
fi
sfw pip install --user --upgrade pip uv
export PATH="$HOME/.local/bin:$PATH"
if ! grep -q 'HOME/.local/bin' "$HOME/.profile"; then
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.profile"
fi
nvidia-smi
python3 --version
uv --version
