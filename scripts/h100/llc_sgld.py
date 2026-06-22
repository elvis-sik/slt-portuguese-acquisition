#!/usr/bin/env python3
"""Self-contained SGLD estimate of the Local Learning Coefficient (LLC) for a
LoRA-finetuned guardrail checkpoint, w.r.t. the Swahili moderation loss.

We avoid depending on devinterp's (version-sensitive) API and implement the standard
localized SGLD directly:

  w <- w - (eps/2)*( nbeta * n * grad L_batch(w) + gamma*(w - w*) ) + sqrt(eps)*N(0,1)
  lambda_hat = nbeta * ( mean_over_draws L_full(w) - L_full(w*) )

L is the moderation LM loss over Swahili (prompt -> "Safety: label") sequences, masked
to the completion (the loss the model was trained to minimise). Positive lambda_hat at a
true local min; we print value, sign, and per-chain agreement (read these, never a label
-- the lesson from our padding-bug debugging). FP32 over all params => needs ~80GB (H100).

Usage:
  python llc_sgld.py --base unsloth/Llama-3.2-3B-Instruct --adapter runs/sw_guardrail/step_00600 \
     --ref data/sw_llc_ref.jsonl --chains 2 --draws 80 --burnin 80 --lr 1e-6 --gamma 100 --nbeta 10 --batch 8
"""
import argparse
import json
import math
import os


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="unsloth/Llama-3.2-3B-Instruct")
    ap.add_argument("--adapter", default="")          # LoRA checkpoint dir; empty = base only
    ap.add_argument("--ref", required=True)            # jsonl with {"input_ids":[...], "labels":[...]} or {"text":...,"label":...}
    ap.add_argument("--out", default="")
    ap.add_argument("--chains", type=int, default=2)
    ap.add_argument("--draws", type=int, default=80)
    ap.add_argument("--burnin", type=int, default=80)
    ap.add_argument("--steps-between", type=int, default=1)
    ap.add_argument("--lr", type=float, default=1e-6)
    ap.add_argument("--gamma", type=float, default=100.0)   # localization
    ap.add_argument("--nbeta", type=float, default=10.0)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--n-data", type=int, default=512)      # effective dataset size n in the SGLD scaling
    ap.add_argument("--seqlen", type=int, default=512)
    args = ap.parse_args()

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(args.base)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(args.base, dtype=torch.float32).to("cuda")
    if args.adapter:
        model = PeftModel.from_pretrained(model, args.adapter)
        model = model.merge_and_unload()   # fold LoRA into base => plain fp32 model at w*
    model.eval()
    for p in model.parameters():
        p.requires_grad_(True)

    # ---- build reference batches (moderation loss, masked to completion) ----
    SYS = ("You are a helpful assistant aiming at input and response moderation. The output format "
           "should be [Explanation: ... \n Safety: safe/unsafe]")
    USER = "Classify the safety of this message as safe or unsafe. Input: {inp} -> "
    rows = [json.loads(l) for l in open(args.ref, encoding="utf-8") if l.strip()][: args.n_data]
    data = []
    for r in rows:
        if "input_ids" in r:
            ids, labels = r["input_ids"][: args.seqlen], r["labels"][: args.seqlen]
        else:
            inp, lab = r["text"], r["label"]
            msgs = [{"role": "system", "content": SYS}, {"role": "user", "content": USER.format(inp=inp)}]
            prompt = tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
            tgt = f"Explanation: This message is {lab}.  Safety: {lab}" + tok.eos_token
            pid = tok(prompt, add_special_tokens=False)["input_ids"]
            tid = tok(tgt, add_special_tokens=False)["input_ids"]
            ids = (pid + tid)[: args.seqlen]
            labels = ([-100] * len(pid) + tid)[: args.seqlen]
        data.append((ids, labels))
    n = len(data)
    print(f"ref examples: {n}")

    def make_batch(idxs):
        ml = max(len(data[i][0]) for i in idxs)
        ii = torch.full((len(idxs), ml), tok.pad_token_id, dtype=torch.long)
        ll = torch.full((len(idxs), ml), -100, dtype=torch.long)
        am = torch.zeros((len(idxs), ml), dtype=torch.long)
        for k, i in enumerate(idxs):
            a, b = data[i]
            ii[k, : len(a)] = torch.tensor(a); ll[k, : len(b)] = torch.tensor(b); am[k, : len(a)] = 1
        return ii.cuda(), am.cuda(), ll.cuda()

    @torch.no_grad()
    def full_loss():
        tot, cnt = 0.0, 0
        for s in range(0, n, args.batch):
            ii, am, ll = make_batch(list(range(s, min(n, s + args.batch))))
            tot += model(input_ids=ii, attention_mask=am, labels=ll).loss.item() * (min(n, s + args.batch) - s)
            cnt += (min(n, s + args.batch) - s)
        return tot / cnt

    L0 = full_loss()
    print(f"init loss L0 = {L0:.5f}")
    w_star = [p.detach().clone() for p in model.parameters()]
    import random
    chain_llcs = []
    for c in range(args.chains):
        rng = random.Random(20260620 + c)
        for p, w0 in zip(model.parameters(), w_star):
            p.data.copy_(w0)
        sampled = []
        total_steps = args.burnin + args.draws * args.steps_between
        for t in range(1, total_steps + 1):
            idx = [rng.randrange(n) for _ in range(args.batch)]
            ii, am, ll = make_batch(idx)
            model.zero_grad(set_to_none=True)
            loss = model(input_ids=ii, attention_mask=am, labels=ll).loss
            loss.backward()
            with torch.no_grad():
                for p, w0 in zip(model.parameters(), w_star):
                    if p.grad is None:
                        continue
                    g = args.nbeta * args.n_data * p.grad + args.gamma * (p.data - w0)
                    noise = torch.randn_like(p) * math.sqrt(args.lr)
                    p.data.add_(-0.5 * args.lr * g + noise)
            if t > args.burnin and (t - args.burnin) % args.steps_between == 0:
                sampled.append(full_loss())
        mean_L = sum(sampled) / len(sampled)
        llc = args.nbeta * (mean_L - L0)
        chain_llcs.append(llc)
        print(f"  chain {c}: lambda_hat = {llc:+.3f}  (mean_sampled_L={mean_L:.5f})")
    for p, w0 in zip(model.parameters(), w_star):
        p.data.copy_(w0)

    res = {"adapter": args.adapter, "L0": L0, "chains": chain_llcs,
           "llc_mean": sum(chain_llcs) / len(chain_llcs),
           "config": {"chains": args.chains, "draws": args.draws, "burnin": args.burnin,
                      "lr": args.lr, "gamma": args.gamma, "nbeta": args.nbeta, "batch": args.batch}}
    print(json.dumps({k: res[k] for k in ("adapter", "L0", "chains", "llc_mean")}, indent=2))
    print("[read the VALUE + SIGN + chain agreement; positive & consistent = valid]")
    if args.out:
        json.dump(res, open(args.out, "w"), indent=2)


if __name__ == "__main__":
    main()
