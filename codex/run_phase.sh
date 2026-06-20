#!/usr/bin/env bash
set -euo pipefail
PROMPT_FILE="${1:?Usage: run_phase.sh PROMPT_FILE [RUN_NAME]}"
RUN_NAME="${2:-$(basename "$PROMPT_FILE" .md)-$(date -u +%Y%m%dT%H%M%SZ)}"
SANDBOX="${CODEX_SANDBOX:-workspace-write}"
if [[ "$SANDBOX" == "danger-full-access" && "${CONFIRM_DANGER:-NO}" != "YES" ]]; then
  echo "Refusing danger-full-access without CONFIRM_DANGER=YES" >&2
  exit 2
fi
OUT_DIR="results/_codex/$RUN_NAME"
mkdir -p "$OUT_DIR"
cp "$PROMPT_FILE" "$OUT_DIR/prompt.md"
codex exec --sandbox "$SANDBOX" --json \
  --output-schema codex/schemas/run_decision.schema.json \
  -o "$OUT_DIR/final_decision.json" \
  "$(cat "$PROMPT_FILE")" | tee "$OUT_DIR/events.jsonl"
echo "Codex output: $OUT_DIR"
