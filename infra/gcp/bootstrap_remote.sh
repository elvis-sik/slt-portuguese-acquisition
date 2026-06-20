#!/usr/bin/env bash
set -euo pipefail
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  build-essential ca-certificates curl git gnupg jq python3 python3-dev python3-pip \
  python3-venv rsync tmux unzip zip

if ! node -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 20 ? 0 : 1)' >/dev/null 2>&1; then
  sudo DEBIAN_FRONTEND=noninteractive apt-get remove -y npm nodejs libnode-dev libnode72 || true
  sudo DEBIAN_FRONTEND=noninteractive apt-get -f install -y || true
  sudo mkdir -p /etc/apt/keyrings
  curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key |
    sudo gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg
  echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" |
    sudo tee /etc/apt/sources.list.d/nodesource.list >/dev/null
  sudo apt-get update
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs
fi

if ! command -v sfw >/dev/null 2>&1; then
  sudo npm install -g sfw
fi
SFW_PATH="$(readlink -f "$(command -v sfw)")"
SFW_ROOT="$(cd "$(dirname "$SFW_PATH")/.." && pwd)"
for sfw_root in "$SFW_ROOT" "$(npm root -g)/sfw" /usr/local/lib/node_modules/sfw /usr/lib/node_modules/sfw; do
  if [[ -d "$sfw_root" ]]; then
    sudo mkdir -p "$sfw_root/.sfw-cache"
    sudo chown -R "$USER:$USER" "$sfw_root/.sfw-cache"
  fi
done
sfw pip install --user --upgrade pip uv
export PATH="$HOME/.local/bin:$PATH"
if ! grep -q 'HOME/.local/bin' "$HOME/.profile"; then
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.profile"
fi
nvidia-smi
python3 --version
uv --version
