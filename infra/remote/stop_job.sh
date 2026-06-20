#!/usr/bin/env bash
set -euo pipefail
NAME="${1:?Usage: stop_job.sh NAME}"
JOB_DIR="${JOB_ROOT:-results/_jobs}/$NAME"
PID="$(cat "$JOB_DIR/pid")"
kill -TERM -- "-$PID" 2>/dev/null || kill -TERM "$PID" 2>/dev/null || true
echo stopped_by_operator > "$JOB_DIR/status"
date -u +%FT%TZ > "$JOB_DIR/end_utc"
