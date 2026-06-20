#!/usr/bin/env bash
set -euo pipefail
NAME=""
MAX_HOURS=""
AUTO_STOP="no"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --name) NAME="$2"; shift 2 ;;
    --max-hours) MAX_HOURS="$2"; shift 2 ;;
    --auto-stop-vm) AUTO_STOP="$2"; shift 2 ;;
    --) shift; break ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
[[ -n "$NAME" && -n "$MAX_HOURS" && $# -gt 0 ]] || {
  echo "Usage: $0 --name NAME --max-hours HOURS --auto-stop-vm yes|no -- COMMAND..." >&2
  exit 2
}
if [[ ! "$NAME" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "Unsafe job name" >&2; exit 2
fi
JOB_DIR="${JOB_ROOT:-results/_jobs}/$NAME"
mkdir -p "$JOB_DIR"
if [[ -f "$JOB_DIR/pid" ]] && kill -0 "$(cat "$JOB_DIR/pid")" 2>/dev/null; then
  echo "Job already running: $NAME" >&2; exit 3
fi
printf '%q ' "$@" > "$JOB_DIR/command.sh"
printf '\n' >> "$JOB_DIR/command.sh"
date -u +%FT%TZ > "$JOB_DIR/start_utc"
rm -f "$JOB_DIR/status" "$JOB_DIR/exit_code" "$JOB_DIR/end_utc"
cat > "$JOB_DIR/runner.sh" <<EOF
#!/usr/bin/env bash
set +e
cd "$(pwd)"
export PYTHONUNBUFFERED=1
/usr/bin/timeout --signal=TERM --kill-after=60s ${MAX_HOURS}h bash "$JOB_DIR/command.sh"
rc=\$?
echo \$rc > "$JOB_DIR/exit_code"
date -u +%FT%TZ > "$JOB_DIR/end_utc"
if [[ \$rc -eq 0 ]]; then echo completed > "$JOB_DIR/status"; else echo failed > "$JOB_DIR/status"; fi
if [[ "$AUTO_STOP" == "yes" ]]; then sudo shutdown -h now; fi
exit \$rc
EOF
chmod +x "$JOB_DIR/runner.sh"
nohup setsid "$JOB_DIR/runner.sh" > "$JOB_DIR/stdout_stderr.log" 2>&1 < /dev/null &
echo $! > "$JOB_DIR/pid"
echo running > "$JOB_DIR/status"
echo "Started $NAME with PID $(cat "$JOB_DIR/pid"). Logs: $JOB_DIR/stdout_stderr.log"
