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

tar \
  --exclude='.git/index.lock' \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
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

echo "Repository copied to ~/$REMOTE_REPO_DIR. Run codex login if authentication is not complete."
