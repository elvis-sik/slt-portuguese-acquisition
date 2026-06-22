#!/usr/bin/env bash
# COMPREHENSIVE LLC-config sweep on the trained checkpoint (step_00600).
# Decision rule: if NO config yields a clean POSITIVE lambda_hat (sampled loss ABOVE L0) here,
# we abandon the LLC and ship the behavioral result.
# Grid (36 configs): batch in {8,32,96=full} x lr in {1e-9,1e-8,1e-7,1e-6} x nbeta in {1,10,30}.
# gamma fixed at 1e4 (first sweep proved it barely matters). chains=1, short, for a fast sign-scan;
# any positive winner gets re-verified with more chains/draws before the trajectory.
cd /slt-portuguese-acquisition || exit 1
mkdir -p results/calib2
CK=runs/sw_guardrail/step_00600
for bs in 8 32 96; do
  for lr in 1e-9 1e-8 1e-7 1e-6; do
    for nb in 1 10 30; do
      t="b${bs}_lr${lr}_nb${nb}"
      echo ">>> $t $(date +%H:%M:%S)"
      python -u scripts/h100/llc_sgld.py --adapter "$CK" --ref data/sw_llc_ref.jsonl \
        --out "results/calib2/$t.json" --chains 1 --draws 8 --burnin 8 --lr "$lr" --gamma 10000 \
        --nbeta "$nb" --batch "$bs" --n-data 96 2>&1 | grep -E "lambda_hat"
    done
  done
done
echo "SWEEP2_DONE $(date)"
