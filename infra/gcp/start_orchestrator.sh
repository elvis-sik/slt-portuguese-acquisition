#!/usr/bin/env bash
# Operator-side convenience: launch the overnight orchestrator on the remote VM.
# The dashboard's "Start Orchestrator" action does the same thing over SSH; this is the
# manual equivalent. Cloud lifecycle and launch stay on the operator machine per AGENTS.md.
#
# Usage:
#   infra/gcp/start_orchestrator.sh [--deadline-hours 8] [--soft 35] [--hard 50] [--no-auto-stop]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"
exec gcloud compute ssh "$VM_NAME" --project="$PROJECT_ID" --zone="$ZONE" -- \
  "cd ~/$REMOTE_REPO_DIR && infra/remote/dashboard_action.sh start-orchestrator $*"
