#!/usr/bin/env bash
# LLC acquisition trajectory across ALL 7 Swahili-guardrail checkpoints, using the GLOBALLY
# FIXED, VERIFIED sampler config (one config for every checkpoint, per AGENTS.md rule 5):
#   template now MATCHES the SFT exactly (system "...any language..." + target "...based on its
#   content..."), so w* sits at a genuine minimum (L0~0.003 at step_600, not 1.04) and SGLD stays
#   UPHILL -> valid positive lambda_hat. Config: lr=1e-8, gamma=1e4, nbeta=1, batch=8,
#   n_data=96, chains=3, draws=30, burnin=30.
#   nbeta=1 is the VERIFIED config (3/3 chains uphill+positive, agreeing); nbeta=20 was rejected
#   because the 20x-stronger gradient pull made one chain escape downhill (chains disagreed).
# Expect lambda_hat to track the ACQUISITION: near-base checkpoints are not yet at a minimum of the
# moderation loss (may read invalid/odd); the trained checkpoints sit at minima with positive lambda.
set -uo pipefail
cd /slt-portuguese-acquisition || exit 1
mkdir -p results/h100_traj
for s in step_00000 step_00100 step_00200 step_00300 step_00400 step_00500 step_00600; do
  echo ">>> LLC $s $(date +%H:%M:%S)"
  python -u scripts/h100/llc_sgld.py --adapter "runs/sw_guardrail/$s" --ref data/sw_llc_ref.jsonl \
    --out "results/h100_traj/llc_$s.json" --chains 3 --draws 30 --burnin 30 \
    --lr 1e-8 --gamma 10000 --nbeta 1 --batch 8 --n-data 96 \
    2>&1 | grep -E "init loss|chain [0-9]:|llc_mean"
done
echo "TRAJ_FIXED_DONE $(date)"
