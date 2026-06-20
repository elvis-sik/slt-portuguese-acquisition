#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

gcloud compute ssh "$VM_NAME" --project="$PROJECT_ID" --zone="$ZONE" --quiet \
  --command='bash -s' < "$SCRIPT_DIR/bootstrap_remote.sh"

gcloud compute ssh "$VM_NAME" --project="$PROJECT_ID" --zone="$ZONE" --quiet \
  --command="mkdir -p ~/$REMOTE_REPO_DIR"

gcloud compute scp --recurse --project="$PROJECT_ID" --zone="$ZONE" \
  "$ROOT"/* "$VM_NAME:~/$REMOTE_REPO_DIR/"

gcloud compute ssh "$VM_NAME" --project="$PROJECT_ID" --zone="$ZONE" --quiet \
  --command="cd ~/$REMOTE_REPO_DIR && git init >/dev/null 2>&1 || true; bash infra/gcp/install_codex_remote.sh"

echo "Repository copied to ~/$REMOTE_REPO_DIR. Run codex login if authentication is not complete."
