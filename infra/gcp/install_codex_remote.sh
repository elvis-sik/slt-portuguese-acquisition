#!/usr/bin/env bash
set -euo pipefail
curl -fsSL https://chatgpt.com/codex/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
command -v codex || {
  echo "Codex was installed but is not on PATH. Start a new login shell and check again." >&2
  exit 1
}
sudo ln -sf "$HOME/.local/bin/codex" /usr/local/bin/codex
codex --version
cat <<'EOF'
Codex is installed. Authenticate interactively on the remote host if needed:
  codex login
Then confirm `codex` is available in a fresh login shell, because the Codex App uses it over SSH.
EOF
