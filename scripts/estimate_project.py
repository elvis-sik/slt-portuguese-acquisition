from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--train-benchmark", type=Path, required=True)
    p.add_argument("--sampler-benchmark", type=Path, required=True)
    p.add_argument("--training-steps", type=int, default=10000)
    p.add_argument("--sampler-chain-steps", type=int, default=31700)
    p.add_argument("--evaluation-hours", type=float, default=1.5)
    p.add_argument("--overhead-factor", type=float, default=1.4)
    p.add_argument("--hourly-rate-usd", type=float, default=1.0)
    p.add_argument("--low-multiplier", type=float, default=0.6)
    p.add_argument("--high-multiplier", type=float, default=2.0)
    p.add_argument("--output-json", type=Path, required=True)
    p.add_argument("--output-md", type=Path, required=True)
    args = p.parse_args()

    train = load(args.train_benchmark)
    sampler = load(args.sampler_benchmark)
    t_train = float(train["seconds_per_step_mean"])
    t_sampler = float(sampler["seconds_per_chain_step_estimate"])
    raw_hours = (args.training_steps * t_train + args.sampler_chain_steps * t_sampler) / 3600
    median = args.overhead_factor * raw_hours + args.evaluation_hours
    low = max(0.1, median * args.low_multiplier)
    high = median * args.high_multiplier
    result = {
        "inputs": {
            "training_steps": args.training_steps,
            "sampler_chain_steps": args.sampler_chain_steps,
            "seconds_per_training_step": t_train,
            "seconds_per_sampler_chain_step": t_sampler,
            "evaluation_hours": args.evaluation_hours,
            "overhead_factor": args.overhead_factor,
            "hourly_rate_usd_planning_assumption": args.hourly_rate_usd,
        },
        "charged_hours": {"low": low, "median": median, "high": high},
        "raw_compute_cost_usd": {
            "low": low * args.hourly_rate_usd,
            "median": median * args.hourly_rate_usd,
            "high": high * args.hourly_rate_usd,
        },
        "planning_warning": "Engineering sensitivity interval, not a statistical confidence interval or official cloud quote.",
        "review_required": median > 10 or median * args.hourly_rate_usd > 35,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    md = f"""# Revised project estimate

- Training step: {t_train:.4f} s
- Sampler chain step: {t_sampler:.4f} s
- Charged hours: {low:.2f} / **{median:.2f}** / {high:.2f} (low/median/high)
- Raw compute cost at ${args.hourly_rate_usd:.2f}/h: ${low*args.hourly_rate_usd:.2f} / **${median*args.hourly_rate_usd:.2f}** / ${high*args.hourly_rate_usd:.2f}
- Review required: {result['review_required']}

This is a sensitivity range, not a statistical confidence interval. Add setup, disk, failed runs, and contingency to the cash budget.
"""
    args.output_md.write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
