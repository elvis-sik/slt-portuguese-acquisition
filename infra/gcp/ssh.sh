#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"
exec gcloud compute ssh "$VM_NAME" --project="$PROJECT_ID" --zone="$ZONE" -- "$@"
