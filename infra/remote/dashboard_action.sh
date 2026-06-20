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
  dashboard_action.sh start-bounded-job --template TEMPLATE --name NAME --max-hours HOURS [--max-epochs N] [--max-steps N] [--max-tokens N]
  dashboard_action.sh write-control --type TYPE --run-id RUN_ID [--checkpoint-id ID] [--new-run-id ID] [--note NOTE]
  dashboard_action.sh start-orchestrator [--deadline-hours H] [--soft USD] [--hard USD] [--no-auto-stop] [--skip-gpu-preflight]
  dashboard_action.sh stop-orchestrator [--kill]
EOF
}

ORCH_DIR="results/_orchestrator"
ORCH_PID="$ORCH_DIR/harness.pid"
ORCH_WATCHDOG_PID="$ORCH_DIR/watchdog.pid"
ORCH_STOP="results/_control/_orchestrator/stop"

# The executor runs danger-full-access and uses the host GPU directly, so confirm the host GPU is
# actually usable before launching. Prevents a false start when the post-boot NVIDIA driver install
# hasn't finished (nvidia-smi/torch.cuda transiently unavailable). Bounded wait ~2 minutes.
gpu_preflight() {
  local pybench=".venv-bench-py311/bin/python"
  [ -x "$pybench" ] || pybench=".venv/bin/python"
  local i
  for i in $(seq 1 12); do
    if nvidia-smi >/dev/null 2>&1; then
      if [ ! -x "$pybench" ] || "$pybench" -c "import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)" >/dev/null 2>&1; then
        echo "GPU preflight OK (attempt $i)."
        return 0
      fi
    fi
    echo "GPU not ready yet (attempt $i/12); waiting 10s..." >&2
    sleep 10
  done
  echo "GPU preflight FAILED after ~2min: nvidia-smi/torch.cuda not ready. Run infra/gcp/wait_for_gpu.sh and retry, or pass --skip-gpu-preflight." >&2
  return 4
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
    max_epochs=""
    max_steps=""
    max_tokens=""
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --template) template="$2"; shift 2 ;;
        --name) name="$2"; shift 2 ;;
        --max-hours) max_hours="$2"; shift 2 ;;
        --max-epochs) max_epochs="$2"; shift 2 ;;
        --max-steps) max_steps="$2"; shift 2 ;;
        --max-tokens) max_tokens="$2"; shift 2 ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
      esac
    done
    [[ -n "$template" && -n "$name" && -n "$max_hours" ]] || { usage; exit 2; }
    safe_name "$name" || { echo "Unsafe job name" >&2; exit 2; }
    case "$template" in
      harmless-status)
        exec env DASHBOARD_MAX_EPOCHS="$max_epochs" DASHBOARD_MAX_STEPS="$max_steps" DASHBOARD_MAX_TOKENS="$max_tokens" \
          "$SCRIPT_DIR/run_bounded_job.sh" --name "$name" --max-hours "$max_hours" --auto-stop-vm no -- \
          bash -lc 'date -u; git status --short --branch; printf "limits: epochs=%s steps=%s tokens=%s\n" "${DASHBOARD_MAX_EPOCHS:-}" "${DASHBOARD_MAX_STEPS:-}" "${DASHBOARD_MAX_TOKENS:-}"; nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits || true'
        ;;
      remote-probe)
        exec env DASHBOARD_MAX_EPOCHS="$max_epochs" DASHBOARD_MAX_STEPS="$max_steps" DASHBOARD_MAX_TOKENS="$max_tokens" \
          "$SCRIPT_DIR/run_bounded_job.sh" --name "$name" --max-hours "$max_hours" --auto-stop-vm no -- \
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
  start-orchestrator)
    deadline_hours=""
    soft=""
    hard=""
    auto_stop_flag=""
    planner_model=""
    planner_effort=""
    exec_model=""
    exec_effort=""
    skip_gpu="no"
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --deadline-hours) deadline_hours="$2"; shift 2 ;;
        --soft) soft="$2"; shift 2 ;;
        --hard) hard="$2"; shift 2 ;;
        --no-auto-stop) auto_stop_flag="--no-auto-stop"; shift ;;
        --planner-model) planner_model="$2"; shift 2 ;;
        --planner-effort) planner_effort="$2"; shift 2 ;;
        --exec-model) exec_model="$2"; shift 2 ;;
        --exec-effort) exec_effort="$2"; shift 2 ;;
        --skip-gpu-preflight) skip_gpu="yes"; shift ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
      esac
    done
    mkdir -p "$ORCH_DIR" "$(dirname "$ORCH_STOP")"
    if [[ -f "$ORCH_PID" ]] && kill -0 "$(cat "$ORCH_PID")" 2>/dev/null; then
      echo "Orchestrator already running (pid $(cat "$ORCH_PID"))." >&2
      exit 3
    fi
    if [[ "$skip_gpu" != "yes" ]]; then gpu_preflight || exit $?; fi
    rm -f "$ORCH_STOP"  # clear any stale cooperative stop signal before launching
    args=(codex/orchestrate.py)
    [[ -n "$deadline_hours" ]] && args+=(--deadline-hours "$deadline_hours")
    [[ -n "$soft" ]] && args+=(--soft-cap "$soft")
    [[ -n "$hard" ]] && args+=(--hard-cap "$hard")
    [[ -n "$auto_stop_flag" ]] && args+=("$auto_stop_flag")
    [[ -n "$planner_model" ]] && args+=(--planner-model "$planner_model")
    [[ -n "$planner_effort" ]] && args+=(--planner-effort "$planner_effort")
    [[ -n "$exec_model" ]] && args+=(--exec-model "$exec_model")
    [[ -n "$exec_effort" ]] && args+=(--exec-effort "$exec_effort")
    nohup setsid python3 "${args[@]}" >> "$ORCH_DIR/harness.log" 2>&1 < /dev/null &
    echo $! > "$ORCH_PID"
    echo "Started orchestrator pid $(cat "$ORCH_PID"). Log: $ORCH_DIR/harness.log"
    # Layer-2 failsafe: VM self-stops 30min after completion/deadline even if the laptop is asleep.
    if [[ -f "$ORCH_WATCHDOG_PID" ]] && kill -0 "$(cat "$ORCH_WATCHDOG_PID")" 2>/dev/null; then
      echo "Completion watchdog already running (pid $(cat "$ORCH_WATCHDOG_PID"))."
    else
      nohup setsid env WATCHDOG_GRACE_MIN="${WATCHDOG_GRACE_MIN:-30}" \
        "$SCRIPT_DIR/completion_watchdog.sh" "$ROOT" >> "$ORCH_DIR/watchdog.log" 2>&1 < /dev/null &
      echo $! > "$ORCH_WATCHDOG_PID"
      echo "Started completion watchdog pid $(cat "$ORCH_WATCHDOG_PID") (grace ${WATCHDOG_GRACE_MIN:-30}min)."
    fi
    ;;
  stop-orchestrator)
    do_kill="no"
    [[ "${1:-}" == "--kill" ]] && do_kill="yes"
    mkdir -p "$(dirname "$ORCH_STOP")"
    : > "$ORCH_STOP"  # cooperative: harness halts at the top of its next tick
    echo "Wrote cooperative stop signal: $ORCH_STOP"
    if [[ "$do_kill" == "yes" && -f "$ORCH_PID" ]]; then
      kill -TERM "$(cat "$ORCH_PID")" 2>/dev/null || true
      echo "Sent TERM to orchestrator pid $(cat "$ORCH_PID")."
    fi
    # Stop the failsafe watchdog so an explicit operator stop does NOT auto-shutdown the VM
    # (you may be stopping in order to debug and want the VM to stay up).
    if [[ -f "$ORCH_WATCHDOG_PID" ]]; then
      kill -TERM "$(cat "$ORCH_WATCHDOG_PID")" 2>/dev/null || true
      rm -f "$ORCH_WATCHDOG_PID"
      echo "Stopped completion watchdog (VM will stay up after this operator stop)."
    fi
    ;;
  *)
    usage
    exit 2
    ;;
esac
