#!/usr/bin/env bash
# Overnight FULL pipeline (laptop-independent). Runs the remaining LLC science to completion, builds
# comparison figures + data tables, then HALTS the VM (stop, not delete; disk preserved). Everything is
# deadline-bounded so the VM is guaranteed to stop before the operator wakes, and an EXIT trap halts the
# VM even if a stage errors — so the machine can never idle-bill overnight.
#
# Priority order (each gated on enough time remaining before the deadline):
#   1. wait for the already-running shuffled-PT control  [essential]
#   2. matched-English control LLC                        [essential]
#   3. seed-A localization sensitivity, loc=300           [rigor]
#   4. seed-A localization sensitivity, loc=30            [rigor]
#   5. figures + data tables, then halt
#
# seed-B replication is intentionally NOT here: training it would re-run final_training.py over ALL
# conditions and clobber the checkpoints these LLC jobs read. It needs a clean dedicated run.
#
# Escape hatch: `touch results/_control/_overnight/cancel_halt` to keep the VM up past the end.
set -uo pipefail
cd "$HOME/slt-portuguese" || exit 1

R="results/02_final_training/final_training_20260620T175233Z_wiki100m"
PY="./.venv-bench-py311/bin/python"
TOK='[400000,800000,1500000,2500000,4000000,6000000,8000000,18000000,27000000,60000000,100000000]'
SUMD="results/03_llc_campaign/_overnight_summary"
DEADLINE_EPOCH="$(date -u -d '2026-06-21T10:30:00Z' +%s)"  # hard halt-by time
STAGE_MIN=140  # need > this many minutes left to start another ~2h LLC run
mkdir -p results/_control/_overnight "$SUMD"
LOG="results/_jobs/_overnight_pipeline.log"
exec >>"$LOG" 2>&1

halt_vm() {
  if [[ -f results/_control/_overnight/cancel_halt ]]; then
    echo "[pipe] EXIT: halt cancelled by operator $(date -u +%FT%TZ)"; return
  fi
  echo "[pipe] EXIT: halting VM $(date -u +%FT%TZ)"; sync; sudo shutdown -h now
}
trap halt_vm EXIT

remaining_min() { echo $(( (DEADLINE_EPOCH - $(date -u +%s)) / 60 )); }
enough() { (( $(remaining_min) > STAGE_MIN )); }

wait_job() {  # block until results/_jobs/$1/status is terminal
  while :; do
    s="$(cat "results/_jobs/$1/status" 2>/dev/null || echo missing)"
    [[ "$s" != "running" && "$s" != "missing" ]] && { echo "[pipe] $1 -> $s $(date -u +%FT%TZ)"; return; }
    sleep 60
  done
}

summarize() {  # $1 llc dir -> $2 out json
  "$PY" - "$1" "$2" <<'PY' || echo "[pipe] summarize failed"
import json, os, glob, sys
src, out = sys.argv[1], sys.argv[2]
rows = []
for f in sorted(glob.glob(os.path.join(src, "running_estimates", "tokens_*.jsonl"))):
    toks = int(os.path.basename(f).replace("tokens_", "").replace(".jsonl", ""))
    final = {}
    for line in open(f):
        line = line.strip()
        if not line:
            continue
        j = json.loads(line); ch = j["chain"]; st = j["step"]
        if ch not in final or st > final[ch][0]:
            final[ch] = (st, j["running_llc"])
    chains = [v[1] for k, v in sorted(final.items())]
    if chains:
        rows.append(dict(tokens=toks, llc_mean=sum(chains)/len(chains), chains=[round(c, 3) for c in chains]))
json.dump(rows, open(out, "w"), indent=2)
print("[pipe] wrote", out, len(rows), "ckpts")
PY
}

mk_selection() {  # $1 condition -> $2 path
  cat > "$2" <<JSON
{"rule_frozen_at_utc":"final","no_final_llc_inspected":true,"primary_condition":"$1","fixed_checkpoint_tokens":$TOK,"adaptive_metric":"none_control_condition","adaptive_bracket_tokens":[1500000,2500000],"selected_checkpoint_tokens":$TOK,"selection_source":"overnight pipeline: same frozen 11-checkpoint subset as structured seed-A; condition-matched non-padded reference; no LLC inspected"}
JSON
}

run_llc() {  # $1 job  $2 condition  $3 selection  $4 reference  $5 outdir  $6 localization
  echo "[pipe] launch $1 (cond=$2 loc=$6) $(date -u +%FT%TZ) remaining=$(remaining_min)min"
  bash infra/remote/run_bounded_job.sh --name "$1" --max-hours 3 --auto-stop-vm no -- \
    "$PY" scripts/llc_campaign.py \
      --final-run-dir "$R" --selection-json "$3" --output-dir "$5" \
      --condition "$2" --reference-path "$4" \
      --num-chains 3 --num-burnin-steps 200 --num-draws 100 --num-steps-bw-draws 2 \
      --lr 1e-5 --n-beta 10 --localization "$6" --batch-size 64 --init-seed 20260620
  wait_job "$1"
}

echo "[pipe] === START $(date -u +%FT%TZ) deadline=10:30Z remaining=$(remaining_min)min ==="

# 1) shuffled control (already running) ----------------------------------------
wait_job llc_shuffled_control
S="$(ls -dt results/03_llc_campaign/shuffled_pt_FINAL_* 2>/dev/null | head -1)"
[[ -n "$S" ]] && summarize "$S" "$SUMD/shuffled_pt_llc.json"

# 2) matched-English control ---------------------------------------------------
if enough; then
  "$PY" scripts/build_packed_reference.py \
    "$R/data_splits/train_matched_en_token_ids.jsonl" \
    "$R/conditions/matched_en/checkpoints/tokens_100000000" \
    "$R/data_splits/sampler_reference_matched_en.jsonl" 256 || echo "[pipe] matched_en ref build failed"
  mk_selection matched_en "$R/llc_selection_matched_en.json"
  run_llc llc_matched_en_control matched_en "$R/llc_selection_matched_en.json" \
    "$R/data_splits/sampler_reference_matched_en.jsonl" \
    "results/03_llc_campaign/matched_en_FINAL_$(date -u +%Y%m%dT%H%M%SZ)" 100
  M="$(ls -dt results/03_llc_campaign/matched_en_FINAL_* 2>/dev/null | head -1)"
  [[ -n "$M" ]] && summarize "$M" "$SUMD/matched_en_llc.json"
else
  echo "[pipe] SKIP matched_en (remaining=$(remaining_min)min)"
fi

# 3) seed-A localization sensitivity, loc=300 (reuse seed-A selection + structured reference) ----
if enough; then
  run_llc llc_seedA_loc300 structured_pt_seed_a "$R/llc_selection_seed_a_final.json" \
    "$R/data_splits/sampler_reference.jsonl" \
    "results/03_llc_campaign/seedA_loc300_$(date -u +%Y%m%dT%H%M%SZ)" 300
  L="$(ls -dt results/03_llc_campaign/seedA_loc300_* 2>/dev/null | head -1)"
  [[ -n "$L" ]] && summarize "$L" "$SUMD/seedA_loc300_llc.json"
else
  echo "[pipe] SKIP loc300 (remaining=$(remaining_min)min)"
fi

# 4) seed-A localization sensitivity, loc=30 -----------------------------------
if enough; then
  run_llc llc_seedA_loc30 structured_pt_seed_a "$R/llc_selection_seed_a_final.json" \
    "$R/data_splits/sampler_reference.jsonl" \
    "results/03_llc_campaign/seedA_loc30_$(date -u +%Y%m%dT%H%M%SZ)" 30
  L="$(ls -dt results/03_llc_campaign/seedA_loc30_* 2>/dev/null | head -1)"
  [[ -n "$L" ]] && summarize "$L" "$SUMD/seedA_loc30_llc.json"
else
  echo "[pipe] SKIP loc30 (remaining=$(remaining_min)min)"
fi

# 5) figures + data tables (non-fatal), then trap halts the VM -----------------
echo "[pipe] building figures + data tables $(date -u +%FT%TZ)"
"$PY" scripts/overnight_report.py "$SUMD" || echo "[pipe] overnight_report failed (non-fatal)"

echo "[pipe] === DONE $(date -u +%FT%TZ); EXIT trap will halt the VM ==="
