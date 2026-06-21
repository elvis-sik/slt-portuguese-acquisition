#!/usr/bin/env python3
"""Aggregate the per-chain running LLC into a per-checkpoint estimate and print the curve.

Reads <campaign_dir>/running_estimates/tokens_*.jsonl (lines: {chain, step, running_llc, ...}),
takes each chain's final cumulative running_llc, averages across chains, and marks which checkpoints
the campaign rejected (from <campaign_dir>/failures/).
"""
import glob
import json
import os
import sys

O = sys.argv[1]
rejected = {os.path.basename(f)[:-5] for f in glob.glob(os.path.join(O, "failures", "*.json"))}


def tok_of(path):
    return int(os.path.basename(path).split("tokens_")[1][:9])


print(f"{'tokens':>11}  {'status':8}  {'llc(mean/chains)':>16}  per-chain")
for f in sorted(glob.glob(os.path.join(O, "running_estimates", "tokens_*.jsonl")), key=tok_of):
    name = os.path.basename(f)[:-6]
    final_by_chain = {}
    for line in open(f):
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        if d.get("running_llc") is not None:
            final_by_chain[d.get("chain")] = d["running_llc"]
    finals = [final_by_chain[c] for c in sorted(final_by_chain)]
    mean = sum(finals) / len(finals) if finals else float("nan")
    status = "REJECTED" if name in rejected else "accepted"
    print(f"{tok_of(f):>11}  {status:8}  {mean:>16.3f}  {[round(x, 2) for x in finals]}")
