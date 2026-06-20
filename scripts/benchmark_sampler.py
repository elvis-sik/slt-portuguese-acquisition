from __future__ import annotations

import argparse
import inspect
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if hasattr(value, "to_dict"):
        try:
            return jsonable(value.to_dict())
        except Exception:
            pass
    return repr(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="devinterp API/performance smoke test")
    parser.add_argument("--model", default="roneneldan/TinyStories-3M")
    parser.add_argument("--sequence-length", type=int, default=128)
    parser.add_argument("--dataset-size", type=int, default=512)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-5)
    parser.add_argument("--n-beta", type=float, default=10.0)
    parser.add_argument("--localization", type=float, default=100.0)
    parser.add_argument("--num-chains", type=int, default=2)
    parser.add_argument("--num-burnin-steps", type=int, default=100)
    parser.add_argument("--num-draws", type=int, default=50)
    parser.add_argument("--num-steps-between-draws", type=int, default=2)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    import numpy as np
    import torch
    from datasets import Dataset
    from devinterp.slt.llc import llc
    from transformers import AutoModelForCausalLM

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for the intended cloud sampler benchmark")
    rng = np.random.default_rng(20260620)
    model = AutoModelForCausalLM.from_pretrained(args.model).to("cuda").float().train()
    vocab = int(model.config.vocab_size)
    data = rng.integers(0, vocab, size=(args.dataset_size, args.sequence_length), dtype=np.int64)
    dataset = Dataset.from_dict({"input_ids": [row.tolist() for row in data]})

    candidate_kwargs = {
        "model": model,
        "dataset": dataset,
        "lr": args.lr,
        "n_beta": args.n_beta,
        "localization": args.localization,
        "batch_size": args.batch_size,
        "num_chains": args.num_chains,
        "num_burnin_steps": args.num_burnin_steps,
        "num_draws": args.num_draws,
        "num_steps_bw_draws": args.num_steps_between_draws,
        "num_steps_between_draws": args.num_steps_between_draws,
    }
    sig = inspect.signature(llc)
    accepts_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
    kwargs = candidate_kwargs if accepts_var_kw else {k: v for k, v in candidate_kwargs.items() if k in sig.parameters}
    # Avoid passing both aliases if the current signature accepts only one through **kwargs.
    if accepts_var_kw:
        kwargs.pop("num_steps_between_draws", None)

    torch.cuda.reset_peak_memory_stats()
    torch.cuda.synchronize()
    start = time.perf_counter()
    result = llc(**kwargs)
    torch.cuda.synchronize()
    wall = time.perf_counter() - start
    approx_steps = args.num_chains * (
        args.num_burnin_steps + args.num_draws * args.num_steps_between_draws
    )
    report = {
        "benchmark": "sampler_smoke",
        "scientific_validity": "none; random-token dataset used for API/performance smoke testing",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "model": args.model,
        "parameter_count": sum(p.numel() for p in model.parameters()),
        "gpu": torch.cuda.get_device_name(0),
        "devinterp_llc_signature": str(sig),
        "kwargs_passed": kwargs,
        "wall_seconds": wall,
        "approx_chain_steps": approx_steps,
        "seconds_per_chain_step_estimate": wall / max(1, approx_steps),
        "peak_memory_bytes": torch.cuda.max_memory_allocated(),
        "result": jsonable(result),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
