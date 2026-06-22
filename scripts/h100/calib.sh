#!/usr/bin/env bash
# Calibrate the SGLD-LLC config on the FULLY FINE-TUNED checkpoint (step_00600), which IS at a
# minimum of the Swahili moderation loss. A correct config must give lambda_hat > 0 there, with the
# sampled loss slightly ABOVE L0 (not wandering downhill) and chains agreeing. Sweep lr-down /
# gamma-up to stop the escape we saw at lr=1e-6 gamma=100.
cd /slt-portuguese-acquisition || exit 1
mkdir -p results/calib
CK=runs/sw_guardrail/step_00600
for cfg in A:1e-7:1000 B:1e-8:1000 C:1e-8:10000 D:3e-9:10000 E:1e-9:10000; do
  t=${cfg%%:*}; r=${cfg#*:}; lr=${r%%:*}; gm=${r#*:}
  echo ">>> $t lr=$lr gamma=$gm $(date +%H:%M:%S)"
  python -u scripts/h100/llc_sgld.py --adapter "$CK" --ref data/sw_llc_ref.jsonl \
    --out "results/calib/$t.json" --chains 2 --draws 15 --burnin 15 --lr "$lr" --gamma "$gm" \
    --nbeta 10 --batch 8 --n-data 96 2>&1 | grep -E "init loss|lambda_hat|mean_sampled"
done
echo "CALIB_DONE $(date)"
