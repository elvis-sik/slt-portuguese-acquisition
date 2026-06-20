#!/usr/bin/env bash
# Failsafe (layer 2): when the orchestrator reaches a terminal state OR the deadline passes, give the
# dashboard a grace window to fetch results, then stop (halt) the VM so it cannot idle-bill. Runs
# detached ON the VM, independent of the operator's laptop. `sudo shutdown -h` halts the guest; GCP
# then shows the instance TERMINATED with the boot disk preserved (stop, never delete).
#
# Does NOT fire on `escalate` (that needs a human) — only on complete / halted_* or a passed deadline.
# Re-checks after the grace window, so an operator relaunch during grace cancels the shutdown.
set -uo pipefail
ROOT="${1:-$HOME/slt-portuguese}"
cd "$ROOT" || exit 1
STATE="results/_orchestrator/state.json"
GRACE_MIN="${WATCHDOG_GRACE_MIN:-30}"

# Prints: terminal | deadline | no
decide() {
  python3 - "$STATE" <<'PY'
import json, sys, time, calendar
try:
    s = json.load(open(sys.argv[1]))
except Exception:
    print("no"); raise SystemExit
if s.get("status", "") in ("complete", "halted_deadline", "halted_budget", "halted_operator"):
    print("terminal"); raise SystemExit
dl = s.get("deadline_at")
if dl:
    try:
        if time.time() > calendar.timegm(time.strptime(dl, "%Y-%m-%dT%H:%M:%SZ")):
            print("deadline"); raise SystemExit
    except Exception:
        pass
print("no")
PY
}

echo "[watchdog] started pid $$ grace=${GRACE_MIN}min root=$ROOT"
while true; do
  if [[ -f "$STATE" ]]; then
    d="$(decide)"
    if [[ "$d" != "no" ]]; then
      echo "[watchdog] $(date -u +%FT%TZ) trigger=$d; waiting ${GRACE_MIN}min for the dashboard to fetch"
      sleep $((GRACE_MIN * 60))
      if [[ "$(decide)" != "no" ]]; then
        echo "[watchdog] $(date -u +%FT%TZ) grace elapsed; sudo shutdown -h now"
        sudo shutdown -h now
        exit 0
      fi
      echo "[watchdog] $(date -u +%FT%TZ) state recovered (relaunched?); standing down"
    fi
  fi
  sleep 30
done
