#!/usr/bin/env bash
# Overnight control chain (laptop-independent, layer-2 safety).
#
# After the already-running shuffled-PT LLC job finishes, run the matched-English control LLC, write
# small summary JSONs for both, then HALT the VM (sudo shutdown -h now => GCP shows TERMINATED with the
# boot disk preserved; stop, never delete). This runs detached ON the VM so the science completes and the
# machine stops even if the operator's laptop sleeps. The operator's local watchers fetch results and open
# the PR while the laptop is awake; if the laptop stops the VM first, that just pre-empts this.
#
# Escape hatch: `touch results/_control/_overnight/cancel_halt` during the grace window to keep the VM up.
set -uo pipefail
cd "$HOME/slt-portuguese" || exit 1
R="results/02_final_training/final_training_20260620T175233Z_wiki100m"
PY="./.venv-bench-py311/bin/python"
SEL_TOKENS='[400000,800000,1500000,2500000,4000000,6000000,8000000,18000000,27000000,60000000,100000000]'
mkdir -p results/_control/_overnight results/03_llc_campaign/_overnight_summary
LOG="results/_jobs/_overnight_chain.log"
exec >>"$LOG" 2>&1
echo "[chain] === start $(date -u +%FT%TZ) pid $$ ==="

wait_job() {  # $1 = job name; block until status file is terminal (not running)
  while :; do
    s="$(cat "results/_jobs/$1/status" 2>/dev/null || echo missing)"
    [[ "$s" != "running" && "$s" != "missing" ]] && { echo "[chain] $1 terminal: $s $(date -u +%FT%TZ)"; return; }
    sleep 60
  done
}

# small per-condition LLC summary (mean + per-chain) from running_estimates/
summarize_llc() {  # $1 = llc output dir ; $2 = out json
  "$PY" - "$1" "$2" <<'PY'
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
print("wrote", out, len(rows), "checkpoints")
PY
}

# ---- 1) wait for the shuffled-PT control already running ----
wait_job llc_shuffled_control
SHUF_OUT="$(ls -dt results/03_llc_campaign/shuffled_pt_FINAL_* 2>/dev/null | head -1)"
[[ -n "$SHUF_OUT" ]] && summarize_llc "$SHUF_OUT" results/03_llc_campaign/_overnight_summary/shuffled_pt_llc.json

# ---- 2) matched-English control: condition-matched non-padded reference ----
echo "[chain] building matched_en reference $(date -u +%FT%TZ)"
"$PY" scripts/build_packed_reference.py \
  "$R/data_splits/train_matched_en_token_ids.jsonl" \
  "$R/conditions/matched_en/checkpoints/tokens_100000000" \
  "$R/data_splits/sampler_reference_matched_en.jsonl" 256

cat > "$R/llc_selection_matched_en.json" <<JSON
{"rule_frozen_at_utc":"final","no_final_llc_inspected":true,"primary_condition":"matched_en","fixed_checkpoint_tokens":$SEL_TOKENS,"adaptive_metric":"none_control_condition","adaptive_bracket_tokens":[1500000,2500000],"selected_checkpoint_tokens":$SEL_TOKENS,"selection_source":"control: same frozen checkpoint subset as structured seed-A; condition-matched non-padded reference; no LLC inspected"}
JSON

TS="$(date -u +%Y%m%dT%H%M%SZ)"
MEN_OUT="results/03_llc_campaign/matched_en_FINAL_$TS"
bash infra/remote/run_bounded_job.sh --name llc_matched_en_control --max-hours 3 --auto-stop-vm no -- \
  "$PY" scripts/llc_campaign.py \
    --final-run-dir "$R" \
    --selection-json "$R/llc_selection_matched_en.json" \
    --output-dir "$MEN_OUT" \
    --condition matched_en \
    --reference-path "$R/data_splits/sampler_reference_matched_en.jsonl" \
    --num-chains 3 --num-burnin-steps 200 --num-draws 100 --num-steps-bw-draws 2 \
    --lr 1e-5 --n-beta 10 --localization 100 --batch-size 64 --init-seed 20260620

wait_job llc_matched_en_control
MEN_OUT="$(ls -dt results/03_llc_campaign/matched_en_FINAL_* 2>/dev/null | head -1)"
[[ -n "$MEN_OUT" ]] && summarize_llc "$MEN_OUT" results/03_llc_campaign/_overnight_summary/matched_en_llc.json

# ---- 3) grace window, then halt (stop, not delete) ----
echo "[chain] all controls done; 20-min grace before halt $(date -u +%FT%TZ)"
for i in $(seq 1 20); do
  if [[ -f results/_control/_overnight/cancel_halt ]]; then
    echo "[chain] halt cancelled by operator $(date -u +%FT%TZ)"; exit 0
  fi
  sleep 60
done
echo "[chain] halting VM now $(date -u +%FT%TZ)"
sudo shutdown -h now
