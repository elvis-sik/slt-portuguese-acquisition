from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Small causal-LM training throughput benchmark")
    parser.add_argument("--model", default="roneneldan/TinyStories-3M")
    parser.add_argument("--sequence-length", type=int, default=128)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--warmup-steps", type=int, default=50)
    parser.add_argument("--steps", type=int, default=200)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--precision", choices=["fp32", "bf16"], default="fp32")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    import torch
    from transformers import AutoModelForCausalLM

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for the intended cloud benchmark")
    torch.manual_seed(20260620)
    device = torch.device("cuda")
    model = AutoModelForCausalLM.from_pretrained(args.model).to(device).train()
    if args.precision == "bf16":
        model = model.to(dtype=torch.bfloat16)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=0.0)
    vocab = int(model.config.vocab_size)
    ids = torch.randint(0, vocab, (args.batch_size, args.sequence_length), device=device)

    def step() -> float:
        optimizer.zero_grad(set_to_none=True)
        out = model(input_ids=ids, labels=ids)
        out.loss.backward()
        optimizer.step()
        return float(out.loss.detach())

    for _ in range(args.warmup_steps):
        step()
    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats()
    durations: list[float] = []
    losses: list[float] = []
    start = time.perf_counter()
    for _ in range(args.steps):
        t0 = time.perf_counter()
        losses.append(step())
        torch.cuda.synchronize()
        durations.append(time.perf_counter() - t0)
    wall = time.perf_counter() - start
    sorted_d = sorted(durations)
    p95 = sorted_d[max(0, min(len(sorted_d) - 1, int(0.95 * len(sorted_d)) - 1))]
    tokens = args.steps * args.batch_size * args.sequence_length
    report = {
        "benchmark": "training",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "model": args.model,
        "parameter_count": sum(p.numel() for p in model.parameters()),
        "gpu": torch.cuda.get_device_name(0),
        "torch_version": torch.__version__,
        "torch_cuda_version": torch.version.cuda,
        "precision": args.precision,
        "sequence_length": args.sequence_length,
        "batch_size": args.batch_size,
        "warmup_steps": args.warmup_steps,
        "measured_steps": args.steps,
        "wall_seconds": wall,
        "seconds_per_step_mean": statistics.mean(durations),
        "seconds_per_step_median": statistics.median(durations),
        "seconds_per_step_p95": p95,
        "tokens_per_second": tokens / wall,
        "peak_memory_bytes": torch.cuda.max_memory_allocated(),
        "first_loss": losses[0],
        "last_loss": losses[-1],
        "warning": "Random-token throughput benchmark; repeat through the real data pipeline before final planning.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
