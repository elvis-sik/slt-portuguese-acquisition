#!/usr/bin/env python3
"""Cost probe: how long would an LLC (SGLD) campaign take on a ~3B model, and does
it even fit on an L4 (24 GB)?

SGLD = SGD-with-noise, so each draw is one forward + backward over a batch. The
dominant cost is exactly that, so we time forward+backward on the target model and
extrapolate to a full LLC config (matching our TinyStories runs: 3 chains, 200
burn-in + 100 draws x (2 steps between) = ~400 steps/chain => ~1200 fwd+bwd /
checkpoint). We try fp32 (our SGLD precision) first; if it OOMs on the L4 we report
that and fall back to fp16 (which would force a precision caveat or a bigger GPU).

Usage: llc_cost_probe.py --model unsloth/Llama-3.2-3B-Instruct --batch 16 --seqlen 128
"""
import argparse
import time


def time_dtype(model_name, dtype, batch, seqlen, steps):
    import torch
    from transformers import AutoModelForCausalLM
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    dt = torch.float32 if dtype == "fp32" else torch.float16
    model = AutoModelForCausalLM.from_pretrained(model_name, dtype=dt).to("cuda")
    model.train()
    vocab = model.config.vocab_size
    ids = torch.randint(0, vocab, (batch, seqlen), device="cuda")
    opt = torch.optim.SGD(model.parameters(), lr=1e-6)  # stand-in for SGLD step cost

    def step():
        opt.zero_grad(set_to_none=True)
        out = model(input_ids=ids, labels=ids)
        out.loss.backward()
        opt.step()

    step(); step()  # warmup
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(steps):
        step()
    torch.cuda.synchronize()
    per_step = (time.perf_counter() - t0) / steps
    peak_gb = torch.cuda.max_memory_allocated() / 1e9
    del model, opt
    torch.cuda.empty_cache()
    return per_step, peak_gb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="unsloth/Llama-3.2-3B-Instruct")
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--seqlen", type=int, default=128)
    ap.add_argument("--steps", type=int, default=10)
    # full-LLC config (matches our TinyStories runs)
    ap.add_argument("--chains", type=int, default=3)
    ap.add_argument("--steps-per-chain", type=int, default=400)
    ap.add_argument("--checkpoints", type=int, default=6)
    args = ap.parse_args()

    import torch
    print(f"GPU: {torch.cuda.get_device_name(0)}  total {torch.cuda.get_device_properties(0).total_memory/1e9:.1f} GB")
    print(f"model={args.model} batch={args.batch} seqlen={args.seqlen}\n")

    steps_per_ckpt = args.chains * args.steps_per_chain
    for dtype in ("fp32", "fp16"):
        try:
            per_step, peak = time_dtype(args.model, dtype, args.batch, args.seqlen, args.steps)
            per_ckpt = per_step * steps_per_ckpt
            print(f"[{dtype}] {per_step*1000:7.1f} ms/step | peak {peak:5.1f} GB | "
                  f"~{per_ckpt/60:5.1f} min/checkpoint | "
                  f"~{per_ckpt*args.checkpoints/3600:4.2f} h for {args.checkpoints} checkpoints")
        except torch.cuda.OutOfMemoryError:
            print(f"[{dtype}] OUT OF MEMORY on this GPU (batch={args.batch}) -> would need fp16/bf16, "
                  f"a smaller batch, gradient checkpointing, or a bigger GPU")
        except Exception as e:
            print(f"[{dtype}] error: {type(e).__name__}: {str(e)[:160]}")


if __name__ == "__main__":
    main()
