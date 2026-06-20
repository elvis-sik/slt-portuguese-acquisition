#!/usr/bin/env python3
"""Re-score saved checkpoints on a Portuguese minimal-pair benchmark (full-sentence log-prob margin).

For each checkpoint, accuracy = fraction of pairs where logprob(grammatical) > logprob(ungrammatical);
also reports the mean margin and per-phenomenon accuracy. Runs on CPU by default (set
CUDA_VISIBLE_DEVICES="" before launching) so it never competes with a training job for the GPU.

Usage:
  CUDA_VISIBLE_DEVICES="" python scripts/score_minimal_pairs.py \
    --run-dir results/02_final_training/<run> --condition structured_pt_seed_a \
    --benchmark data/eval/pt_minimal_pairs.jsonl --output results/eval_minimal_pairs/<run>_<cond>.json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
from collections import defaultdict

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


def sent_logprob(model, tok, text: str) -> float:
    ids = tok(text, return_tensors="pt").input_ids
    with torch.no_grad():
        logits = model(ids).logits
    logp = torch.log_softmax(logits[:, :-1, :], dim=-1)
    tgt = ids[:, 1:]
    return logp.gather(-1, tgt.unsqueeze(-1)).squeeze(-1).sum().item()


def score_checkpoint(ckpt_dir: str, pairs: list[dict]) -> dict:
    tok = AutoTokenizer.from_pretrained(ckpt_dir)
    model = AutoModelForCausalLM.from_pretrained(ckpt_dir, torch_dtype=torch.float32)
    model.eval()
    correct, margins = 0, []
    per = defaultdict(lambda: [0, 0])
    for p in pairs:
        m = sent_logprob(model, tok, p["grammatical"]) - sent_logprob(model, tok, p["ungrammatical"])
        ok = m > 0
        correct += ok
        margins.append(m)
        per[p["phenomenon"]][0] += ok
        per[p["phenomenon"]][1] += 1
    n = len(pairs)
    return {
        "accuracy": round(correct / n, 4),
        "mean_margin": round(sum(margins) / n, 4),
        "n": n,
        "per_phenomenon": {k: round(v[0] / v[1], 3) for k, v in sorted(per.items())},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--condition", default="structured_pt_seed_a")
    ap.add_argument("--benchmark", default="data/eval/pt_minimal_pairs.jsonl")
    ap.add_argument("--output", required=True)
    a = ap.parse_args()

    pairs = [json.loads(l) for l in open(a.benchmark, encoding="utf-8") if l.strip()]
    ckpts = sorted(
        glob.glob(os.path.join(a.run_dir, "conditions", a.condition, "checkpoints", "tokens_*")),
        key=lambda d: int(re.search(r"tokens_(\d+)", d).group(1)),
    )
    rows = []
    for c in ckpts:
        toks = int(re.search(r"tokens_(\d+)", c).group(1))
        r = score_checkpoint(c, pairs)
        r["tokens"] = toks
        rows.append(r)
        print(f"  tokens {toks:>9} -> acc {r['accuracy']:.3f}  mean_margin {r['mean_margin']:+.3f}")
    os.makedirs(os.path.dirname(a.output), exist_ok=True)
    json.dump({"condition": a.condition, "benchmark_n": len(pairs), "checkpoints": rows},
              open(a.output, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"wrote {a.output}")


if __name__ == "__main__":
    main()
