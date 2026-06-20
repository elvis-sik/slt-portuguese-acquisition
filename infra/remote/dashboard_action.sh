#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT"

safe_name() {
  [[ "$1" =~ ^[A-Za-z0-9._-]+$ ]]
}

usage() {
  cat >&2 <<'EOF'
Usage:
  dashboard_action.sh probe
  dashboard_action.sh start-bounded-job --template TEMPLATE --name NAME --max-hours HOURS
  dashboard_action.sh write-control --type TYPE --run-id RUN_ID [--checkpoint-id ID] [--new-run-id ID] [--note NOTE]
EOF
}

if [[ $# -lt 1 ]]; then
  usage
  exit 2
fi

cmd="$1"
shift

case "$cmd" in
  probe)
    exec "$SCRIPT_DIR/dashboard_probe.sh"
    ;;
  start-bounded-job)
    template=""
    name=""
    max_hours=""
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --template) template="$2"; shift 2 ;;
        --name) name="$2"; shift 2 ;;
        --max-hours) max_hours="$2"; shift 2 ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
      esac
    done
    [[ -n "$template" && -n "$name" && -n "$max_hours" ]] || { usage; exit 2; }
    safe_name "$name" || { echo "Unsafe job name" >&2; exit 2; }
    case "$template" in
      harmless-status)
        exec "$SCRIPT_DIR/run_bounded_job.sh" --name "$name" --max-hours "$max_hours" --auto-stop-vm no -- \
          bash -lc 'date -u; git status --short --branch; nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits || true'
        ;;
      remote-probe)
        exec "$SCRIPT_DIR/run_bounded_job.sh" --name "$name" --max-hours "$max_hours" --auto-stop-vm no -- \
          "$SCRIPT_DIR/dashboard_probe.sh"
        ;;
      *)
        echo "Unknown template: $template" >&2
        exit 2
        ;;
    esac
    ;;
  write-control)
    type=""
    run_id=""
    checkpoint_id=""
    new_run_id=""
    note=""
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --type) type="$2"; shift 2 ;;
        --run-id) run_id="$2"; shift 2 ;;
        --checkpoint-id) checkpoint_id="$2"; shift 2 ;;
        --new-run-id) new_run_id="$2"; shift 2 ;;
        --note) note="$2"; shift 2 ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
      esac
    done
    [[ -n "$type" && -n "$run_id" ]] || { usage; exit 2; }
    safe_name "$run_id" || { echo "Unsafe run id" >&2; exit 2; }
    ts="$(date -u +%Y%m%dT%H%M%SZ)"
    out_dir="results/_control/$run_id/commands"
    mkdir -p "$out_dir"
    python3 - "$type" "$run_id" "$checkpoint_id" "$new_run_id" "$note" "$ts" "$out_dir/${ts}_${type}.json" <<'PY'
from __future__ import annotations

import json
import sys

kind, run_id, checkpoint_id, new_run_id, note, ts, out_path = sys.argv[1:]
payload = {
    "type": kind,
    "run_id": run_id,
    "checkpoint_id": checkpoint_id or None,
    "new_run_id": new_run_id or None,
    "note": note,
    "created_at": ts,
}
with open(out_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)
    handle.write("\n")
print(out_path)
PY
    ;;
  *)
    usage
    exit 2
    ;;
esac
