#!/usr/bin/env bash
# One-shot H100-pod pipeline: Swahili guardrail acquisition (behavior + LLC).
# Assumes a RunPod "PyTorch 2.x" image (torch+CUDA present). Run from this repo root:
#   bash scripts/h100/run_on_pod.sh
# Behavioral curve is produced FIRST (low risk); LLC per checkpoint is the stretch.
set -uo pipefail
cd "$(dirname "$0")/../.."   # repo root
HD=scripts/h100
OUT=runs/sw_guardrail
mkdir -p "$OUT" data results/h100

echo "=== deps ==="
pip install -q -U "transformers>=4.45" peft accelerate datasets || { echo "pip failed"; exit 1; }

echo "=== get Swahili moderation data (from public MrGuard repo) ==="
[ -d mrguard ] || git clone --depth 1 https://github.com/yangy96/mrguard mrguard
SW=mrguard/benchmark_data/moderation/moderation_ai_translation_sw.jsonl
[ -f "$SW" ] || { echo "Swahili data not found at $SW"; find mrguard -iname '*sw*moderation*' -o -iname '*moderation*sw*'; exit 1; }

echo "=== prep: split into train / eval / llc-ref (derive binary label, keep EN control) ==="
python - "$SW" <<'PY'
import json, sys, random
rows=[json.loads(l) for l in open(sys.argv[1],encoding="utf-8") if l.strip()]
CAT=["S","H","V","HR","SH","S3","H2","V2"]
def lab(r): return "unsafe" if any(int(r.get(c,0)) for c in CAT) else "safe"
recs=[{"text":r.get("translated_prompt","").strip(),"en":r.get("prompt","").strip(),"label":lab(r)}
      for r in rows if r.get("translated_prompt")]
random.Random(0).shuffle(recs)
ne=min(150,len(recs)//5)
ev,tr=recs[:ne],recs[ne:]
open("data/sw_eval.jsonl","w",encoding="utf-8").write("\n".join(json.dumps(r,ensure_ascii=False) for r in ev))
# SFT trains directly off the moderation jsonl; LLC ref = train-distribution examples (what the model minimised)
open("data/sw_llc_ref.jsonl","w",encoding="utf-8").write("\n".join(json.dumps(r,ensure_ascii=False) for r in tr[:512]))
print(f"train≈{len(tr)} eval={len(ev)} llc_ref={min(512,len(tr))}  unsafe-frac(eval)={sum(r['label']=='unsafe' for r in ev)/len(ev):.2f}")
PY

echo "=== SFT (saves adapters at log-spaced checkpoints, incl. step 0) ==="
python "$HD/swahili_guardrail_sft.py" --data "$SW" --out "$OUT" --max-steps 600 --n-checkpoints 6 --batch 8 || exit 1

echo "=== per-checkpoint BEHAVIOR (low-risk result first) ==="
for d in $(ls -d "$OUT"/step_* | sort); do
  s=$(basename "$d")
  python "$HD/sw_benchmark.py" --adapter "$d" --eval data/sw_eval.jsonl --out "results/h100/bench_$s.json" --langs sw,en
done
echo "--- behavior summary ---"; for f in results/h100/bench_step_*.json; do echo "$f"; cat "$f"; done

echo "=== per-checkpoint LLC (stretch; fp32 needs ~80GB) — start cheap to calibrate ==="
for d in $(ls -d "$OUT"/step_* | sort); do
  s=$(basename "$d")
  echo ">>> LLC $s"
  /usr/bin/time -v python "$HD/llc_sgld.py" --adapter "$d" --ref data/sw_llc_ref.jsonl \
     --out "results/h100/llc_$s.json" --chains 2 --draws 60 --burnin 60 --lr 1e-6 --gamma 100 --nbeta 10 --batch 8 \
     2>&1 | grep -E "lambda_hat|init loss|llc_mean|Elapsed|Maximum resident" || true
done
echo "=== DONE. behavior: results/h100/bench_*.json ; LLC: results/h100/llc_*.json ==="
