#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"
gcloud compute config-ssh --project="$PROJECT_ID" --quiet
ALIAS="${VM_NAME}.${ZONE}.${PROJECT_ID}"
echo "Gcloud SSH config updated. Test the concrete alias:"
echo "  ssh $ALIAS"
echo "Then add/enable that SSH host in Codex App Settings > Connections and select:"
echo "  ~/$REMOTE_REPO_DIR"
echo "If the generated alias differs, inspect concrete Host entries in ~/.ssh/config."
