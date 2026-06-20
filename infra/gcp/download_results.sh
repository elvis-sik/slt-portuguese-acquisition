#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"
mkdir -p "$ROOT/downloaded_results"
gcloud compute scp --recurse --project="$PROJECT_ID" --zone="$ZONE" \
  "$VM_NAME:~/$REMOTE_REPO_DIR/results" "$ROOT/downloaded_results/"
