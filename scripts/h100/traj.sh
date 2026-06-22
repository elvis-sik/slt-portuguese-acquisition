#!/usr/bin/env bash
# LLC trajectory across the Swahili-guardrail acquisition, using the calibrated config D
# (lr=3e-9, gamma=10000): the sampler stays local (~97% of L0) with tight chains. We expect
# lambda_hat to RISE from strongly-negative at the base (not at a minimum of the moderation
# loss) toward ~0 at the trained checkpoint (a flat minimum has formed).
cd /slt-portuguese-acquisition || exit 1
mkdir -p results/h100
for s in step_00000 step_00200 step_00400 step_00600; do
  echo ">>> LLC $s $(date +%H:%M:%S)"
  python -u scripts/h100/llc_sgld.py --adapter "runs/sw_guardrail/$s" --ref data/sw_llc_ref.jsonl \
    --out "results/h100/llc_$s.json" --chains 3 --draws 20 --burnin 20 --lr 3e-9 --gamma 10000 \
    --nbeta 10 --batch 8 --n-data 96 2>&1 | grep -E "init loss|lambda_hat|llc_mean"
done
echo "TRAJ_DONE $(date)"
