#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"
if [[ "${CONFIRM_DELETE:-NO}" != "YES" ]]; then
  echo "Refusing deletion. Download results, then set CONFIRM_DELETE=YES." >&2
  exit 2
fi
gcloud compute instances delete "$VM_NAME" --project="$PROJECT_ID" --zone="$ZONE" --quiet
