#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"
ARCHIVE="$(mktemp -t slt-portuguese-repo.XXXXXX.tar.gz)"
cleanup() {
  rm -f "$ARCHIVE"
}
trap cleanup EXIT

COPYFILE_DISABLE=1 tar \
  --exclude='.git/index.lock' \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='._*' \
  --exclude='__MACOSX' \
  --exclude='.cache' \
  --exclude='wandb' \
  --exclude='.env.local' \
  --exclude='infra/gcp/.env' \
  --exclude='infra/gcp/.env.local' \
  -C "$ROOT" -czf "$ARCHIVE" .

gcloud compute ssh "$VM_NAME" --project="$PROJECT_ID" --zone="$ZONE" --quiet \
  --command='bash -s' < "$SCRIPT_DIR/bootstrap_remote.sh"

gcloud compute ssh "$VM_NAME" --project="$PROJECT_ID" --zone="$ZONE" --quiet \
  --command="mkdir -p ~/$REMOTE_REPO_DIR"

gcloud compute scp --project="$PROJECT_ID" --zone="$ZONE" \
  "$ARCHIVE" "$VM_NAME:/tmp/slt-portuguese-repo.tar.gz"

gcloud compute ssh "$VM_NAME" --project="$PROJECT_ID" --zone="$ZONE" --quiet \
  --command="tar -xzf /tmp/slt-portuguese-repo.tar.gz -C ~/$REMOTE_REPO_DIR && rm -f /tmp/slt-portuguese-repo.tar.gz && cd ~/$REMOTE_REPO_DIR && bash infra/gcp/install_codex_remote.sh"

echo "Repository copied to ~/$REMOTE_REPO_DIR."

# Optionally install the OpenAI API key from 1Password so Codex can authenticate
# headlessly. Runs only when `op` is available and OPENAI_API_KEY_OP_REF is set in
# the repo-root .env.local. Otherwise, fall back to interactive `codex login`.
OP_REF="$(set -a; [ -f "$ROOT/.env.local" ] && . "$ROOT/.env.local"; printf '%s' "${OPENAI_API_KEY_OP_REF:-}")"
if [[ -n "$OP_REF" ]] && command -v op >/dev/null 2>&1; then
  echo "Installing Codex API key from 1Password ($OP_REF)..."
  bash "$SCRIPT_DIR/push_codex_secret.sh"
else
  echo "Codex authentication not yet installed. Either:"
  echo "  - set OPENAI_API_KEY_OP_REF in .env.local and run infra/gcp/push_codex_secret.sh, or"
  echo "  - run 'codex login' interactively on the VM."
fi
