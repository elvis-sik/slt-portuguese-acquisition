#!/usr/bin/env python3
"""Build a NON-PADDED LLC reference set from the real training chunks.

The original sampler_reference.jsonl used short OPUS sentences padded ~90% with eos (unmasked) — so
the LLC measured a loss the model was never optimised for, giving negative estimates everywhere. Here
we take full-length (>= seqlen-token) chunks straight from the training token-id stream and decode them
to text, so when llc_campaign re-tokenises and truncates to seqlen there is essentially no padding and
the loss matches what the model actually minimised.

Usage: build_packed_reference.py <train_token_ids.jsonl> <checkpoint_dir> <out.jsonl> [N]
"""
import json
import sys

from transformers import AutoTokenizer

src, ckpt, out = sys.argv[1], sys.argv[2], sys.argv[3]
N = int(sys.argv[4]) if len(sys.argv) > 4 else 256
SEQLEN = 128

tok = AutoTokenizer.from_pretrained(ckpt, local_files_only=True)
rows = []
with open(src) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        ids = json.loads(line).get("input_ids")
        if not ids or len(ids) < SEQLEN:
            continue
        text = tok.decode(ids[:SEQLEN], skip_special_tokens=True)
        if len(tok(text)["input_ids"]) >= SEQLEN:  # ensure full-length after re-encode (no padding)
            rows.append({"pt": text, "id": f"trainchunk_{len(rows):06d}", "source": "train_structured_pt"})
        if len(rows) >= N:
            break

with open(out, "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"wrote {len(rows)} non-padded reference chunks; first re-encoded token len = {len(tok(rows[0]['pt'])['input_ids'])}")
