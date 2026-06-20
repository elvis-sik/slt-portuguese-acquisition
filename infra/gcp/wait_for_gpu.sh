#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-30}"
SLEEP_SECONDS="${SLEEP_SECONDS:-20}"
for ((i=1; i<=MAX_ATTEMPTS; i++)); do
  echo "[$i/$MAX_ATTEMPTS] checking SSH and nvidia-smi..."
  if gcloud compute ssh "$VM_NAME" --project="$PROJECT_ID" --zone="$ZONE" \
      --quiet --command='nvidia-smi' >/tmp/slt_nvidia_smi.out 2>/tmp/slt_nvidia_smi.err; then
    cat /tmp/slt_nvidia_smi.out
    echo "GPU ready."
    exit 0
  fi
  sleep "$SLEEP_SECONDS"
done
echo "GPU was not ready. Inspect serial output and /opt/google/cuda-installer on the VM." >&2
cat /tmp/slt_nvidia_smi.err >&2 || true
exit 1
