#!/usr/bin/env bash
# Fetch result artifacts from the VM to ./downloaded_results. By default pulls everything light and
# human-facing — reports, figures (PNG/PDF/SVG), source tables, JSON/CSV/logs — and SKIPS the heavy
# checkpoints and zarr traces. Pass --with-checkpoints to include those too.
#
# Usage:
#   infra/gcp/download_results.sh                 # light: reports, figures, pdf, tables, logs
#   infra/gcp/download_results.sh --with-checkpoints
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

WITH_CHECKPOINTS="no"
[[ "${1:-}" == "--with-checkpoints" ]] && WITH_CHECKPOINTS="yes"

DEST="$ROOT/downloaded_results"
mkdir -p "$DEST"

# Prefer the gcloud-configured SSH alias (rsync needs a plain host). Fall back to a recursive scp.
HOST="${DASHBOARD_SSH_HOST:-${VM_NAME}.${ZONE}.${PROJECT_ID}}"
REMOTE="$HOST:${REMOTE_REPO_DIR}/results/"

includes=(--include='*/' --include='*.json' --include='*.jsonl' --include='*.csv' --include='*.md'
  --include='*.txt' --include='*.log' --include='*.png' --include='*.pdf' --include='*.svg')

if command -v rsync >/dev/null 2>&1 && ssh -o BatchMode=yes -o ConnectTimeout=8 "$HOST" true 2>/dev/null; then
  if [[ "$WITH_CHECKPOINTS" == "yes" ]]; then
    rsync -azh --info=progress2 "$REMOTE" "$DEST/results/"
  else
    rsync -azh --info=progress2 --prune-empty-dirs "${includes[@]}" \
      --exclude='checkpoints/**' --exclude='cache/**' --exclude='*.zarr/**' --exclude='*' \
      "$REMOTE" "$DEST/results/"
  fi
  echo "Downloaded to $DEST/results/ (checkpoints: $WITH_CHECKPOINTS)."
else
  echo "rsync/ssh alias unavailable; falling back to full recursive scp (includes checkpoints)." >&2
  gcloud compute scp --recurse --project="$PROJECT_ID" --zone="$ZONE" \
    "$VM_NAME:~/${REMOTE_REPO_DIR}/results" "$DEST/"
fi
