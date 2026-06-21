#!/usr/bin/env bash
# seed-B replication pipeline (laptop-independent, deadline-bounded, self-halting).
#   1. train structured_pt_seed_b to 100M into the EXISTING run dir (--only-conditions; reuses the
#      identical data splits, distinct seed offset 404 => true replication, other conditions untouched)
#   2. LLC trajectory on seed-B checkpoints (condition-matched reference = the structured non-padded
#      reference, since seed-B trains on the same structured corpus as seed-A)
#   3. write seed-B behavioral (BPB) + LLC summaries, then HALT the VM (stop, not delete).
# EXIT-trap halts the VM even on error; a deadline guards against overrun.
# Escape hatch: touch results/_control/_overnight/cancel_halt
set -uo pipefail
cd "$HOME/slt-portuguese" || exit 1

R="results/02_final_training/final_training_20260620T175233Z_wiki100m"
PY="./.venv-bench-py311/bin/python"
TOK='[400000,800000,1500000,2500000,4000000,6000000,8000000,18000000,27000000,60000000,100000000]'
SUMD="results/03_llc_campaign/_overnight_summary"
DEADLINE_EPOCH="$(date -u -d '2026-06-21T20:00:00Z' +%s)"
mkdir -p results/_control/_overnight "$SUMD"
LOG="results/_jobs/_seedb_pipeline.log"
exec >>"$LOG" 2>&1

halt_vm() {
  if [[ -f results/_control/_overnight/cancel_halt ]]; then echo "[seedb] EXIT: halt cancelled"; return; fi
  echo "[seedb] EXIT: halting VM $(date -u +%FT%TZ)"; sync; sudo shutdown -h now
}
trap halt_vm EXIT

remaining_min() { echo $(( (DEADLINE_EPOCH - $(date -u +%s)) / 60 )); }
wait_job() {
  while :; do
    s="$(cat "results/_jobs/$1/status" 2>/dev/null || echo missing)"
    [[ "$s" != "running" && "$s" != "missing" ]] && { echo "[seedb] $1 -> $s $(date -u +%FT%TZ)"; return; }
    sleep 60
  done
}
summarize_llc() {
  "$PY" - "$1" "$2" <<'PY' || echo "[seedb] summarize failed"
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
print("[seedb] wrote", out, len(rows), "ckpts")
PY
}
summarize_bpb() {  # $1 condition dir -> $2 out json (also prints first/last for the log)
  "$PY" - "$1" "$2" <<'PY' || echo "[seedb] bpb summary failed"
import json, os, glob, sys
cdir, out = sys.argv[1], sys.argv[2]
rows = []
for f in sorted(glob.glob(os.path.join(cdir, "evaluations", "tokens_*.json"))):
    d = json.load(open(f))
    rows.append(dict(tokens=d["target_tokens"], pt_bpb=d["pt_validation"]["bpb"], en_bpb=d["english_retention"]["bpb"]))
json.dump(rows, open(out, "w"), indent=2)
if rows:
    print("[seedb] PT BPB first=%.3f last=%.3f (learned if last<<first)" % (rows[0]["pt_bpb"], rows[-1]["pt_bpb"]))
PY
}

echo "[seedb] === START $(date -u +%FT%TZ) deadline=20:00Z remaining=$(remaining_min)min ==="

# 1) train seed-B only. Copy frozen config to /tmp so the in-place copy onto itself can't SameFileError.
cp "$R/frozen_config.json" /tmp/seedb_config.json
bash infra/remote/run_bounded_job.sh --name train_seed_b --max-hours 2 --auto-stop-vm no -- \
  "$PY" scripts/final_training.py \
    --config /tmp/seedb_config.json --output-dir "$R" --only-conditions structured_pt_seed_b
wait_job train_seed_b
summarize_bpb "$R/conditions/structured_pt_seed_b" "$SUMD/seed_b_bpb.json"

NB="$(ls $R/conditions/structured_pt_seed_b/checkpoints/ 2>/dev/null | wc -l)"
echo "[seedb] seed-B checkpoints present: $NB"
if (( NB < 11 )); then
  echo "[seedb] WARNING: seed-B training looks incomplete ($NB checkpoints); skipping LLC."
  exit 0  # trap halts
fi

# GUARANTEE seed-B is a genuine replication, not a duplicate of seed-A: the data-order-seed bug
# (fixed 2026-06-21) previously produced byte-identical weights. Refuse the LLC if they match.
identical=0
for t in tokens_000400000 tokens_002500000 tokens_100000000; do
  HA="$(sha256sum "$R/conditions/structured_pt_seed_a/checkpoints/$t/model.safetensors" 2>/dev/null | cut -d" " -f1)"
  HB="$(sha256sum "$R/conditions/structured_pt_seed_b/checkpoints/$t/model.safetensors" 2>/dev/null | cut -d" " -f1)"
  if [ -n "$HA" ] && [ "$HA" = "$HB" ]; then echo "[seedb] $t IDENTICAL to seed-A"; identical=$((identical+1)); else echo "[seedb] $t differs (A=${HA:0:12} B=${HB:0:12})"; fi
done
if (( identical > 0 )); then
  echo "[seedb] ABORT: seed-B is NOT independent of seed-A ($identical/3 checkpoints identical). Not a replication; skipping LLC. Investigate the seed/data-order fix."
  exit 0  # trap halts
fi
echo "[seedb] VERIFIED: seed-B genuinely differs from seed-A at all sampled checkpoints -> valid replication."

# 2) seed-B LLC (condition-matched reference = the structured non-padded reference)
cat > "$R/llc_selection_seed_b.json" <<JSON
{"rule_frozen_at_utc":"final","no_final_llc_inspected":true,"primary_condition":"structured_pt_seed_b","fixed_checkpoint_tokens":$TOK,"adaptive_metric":"replication","adaptive_bracket_tokens":[1500000,2500000],"selected_checkpoint_tokens":$TOK,"selection_source":"replication: same frozen 11-checkpoint subset and structured reference as seed-A; no LLC inspected"}
JSON
TS="$(date -u +%Y%m%dT%H%M%SZ)"
SB_OUT="results/03_llc_campaign/seed_b_FINAL_$TS"
bash infra/remote/run_bounded_job.sh --name llc_seed_b_final --max-hours 3 --auto-stop-vm no -- \
  "$PY" scripts/llc_campaign.py \
    --final-run-dir "$R" --selection-json "$R/llc_selection_seed_b.json" --output-dir "$SB_OUT" \
    --condition structured_pt_seed_b --reference-path "$R/data_splits/sampler_reference.jsonl" \
    --num-chains 3 --num-burnin-steps 200 --num-draws 100 --num-steps-bw-draws 2 \
    --lr 1e-5 --n-beta 10 --localization 100 --batch-size 64 --init-seed 20260620
wait_job llc_seed_b_final
SB="$(ls -dt results/03_llc_campaign/seed_b_FINAL_* 2>/dev/null | head -1)"
[[ -n "$SB" ]] && summarize_llc "$SB" "$SUMD/seed_b_llc.json"

echo "[seedb] === DONE $(date -u +%FT%TZ); EXIT trap will halt the VM ==="
