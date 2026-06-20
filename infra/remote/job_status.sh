#!/usr/bin/env bash
set -euo pipefail
NAME="${1:?Usage: job_status.sh NAME}"
JOB_DIR="${JOB_ROOT:-results/_jobs}/$NAME"
for f in status pid start_utc end_utc exit_code; do
  if [[ -f "$JOB_DIR/$f" ]]; then printf '%-10s %s\n' "$f" "$(cat "$JOB_DIR/$f")"; fi
done
if [[ -f "$JOB_DIR/pid" ]] && kill -0 "$(cat "$JOB_DIR/pid")" 2>/dev/null; then
  echo "process    alive"
else
  echo "process    not alive"
fi
echo "--- last 40 log lines ---"
tail -n 40 "$JOB_DIR/stdout_stderr.log" 2>/dev/null || true
