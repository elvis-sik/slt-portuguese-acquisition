# Infrastructure Gate Phase Report

- Run ID: `infra_gate_20260620T052138Z`
- Source commit used for GPU jobs: `e2dc7f13d27a3eccdc9311d060d6741b4e697399`
- State commit after phase completion: `4a73f86`
- Python: `.venv-bench-py311/bin/python`
- Model: `roneneldan/TinyStories-3M`
- GPU: NVIDIA L4, driver 610.43.02, 23,689,363,456 bytes CUDA memory

## Commands

All GPU jobs were launched through `infra/remote/run_bounded_job.sh` with `JOB_ROOT=results/00_infrastructure_gate/infra_gate_20260620T052138Z/jobs`.

- `scripts/check_environment.py --model roneneldan/TinyStories-3M --output .../check_environment.json`
- `scripts/tinystories_gate_loop.py --model roneneldan/TinyStories-3M --output-dir .../tinystories_loop --sequence-length 64 --batch-size 4 --train-steps 2 --device cuda`
- `scripts/benchmark_train.py --model roneneldan/TinyStories-3M --sequence-length 64 --batch-size 32 --warmup-steps 50 --steps 200 --output .../train_seq64.json`
- `scripts/benchmark_train.py --model roneneldan/TinyStories-3M --sequence-length 128 --batch-size 32 --warmup-steps 50 --steps 200 --output .../train_seq128.json`
- `scripts/benchmark_sampler.py --model roneneldan/TinyStories-3M --sequence-length 128 --batch-size 32 --num-chains 2 --num-burnin-steps 100 --num-draws 50 --num-steps-between-draws 2 --output .../sampler_smoke.json`
- `scripts/estimate_project.py --train-benchmark .../train_seq128.json --sampler-benchmark .../sampler_smoke.json --hourly-rate-usd 1.00 --output-json .../project_estimate.json --output-md .../project_estimate.md`

## Evidence

- CUDA visible to `nvidia-smi` and PyTorch; model forward/backward ran on `cuda`.
- TinyStories train-save-reload-evaluate-sample loop completed and wrote checkpoint hashes plus `generated_sample.txt`.
- Seq64 benchmark: 0.0389s mean step, 52,661 tokens/s, 91.1% VRAM headroom.
- Seq128 benchmark: 0.0744s mean step, 55,082 tokens/s, 82.3% VRAM headroom.
- Sampler smoke: 56.39s wall, 0.1410s estimated per chain step, 9,547,222 bytes of zarr traces, 85.6% VRAM headroom.
- All bounded jobs have `command.sh`, `stdout_stderr.log`, `status`, `exit_code`, `start_utc`, and `end_utc` files.

## Runtime And Cost

- Fresh run wall time: 151s, or 0.0419 charged GPU-hours.
- Cumulative infrastructure-gate bookkeeping estimate after prior diagnostics: 0.0919 GPU-hours / $0.0919 at $1.00/h.
- Revised project estimate: 2.12 / 3.53 / 7.05 charged hours and $2.12 / $3.53 / $7.05 low/median/high.
- Review required: false.

## Uncertainty And Failure Modes

The sampler smoke uses random tokens and is not a valid LLC estimate. The training benchmark is a synthetic smoke benchmark; the pilot should repeat timing through the real data pipeline when available. Prior CUDA failures are retained as diagnostics, but this gate decision uses only the fresh GPU-visible run.

## Gate Decision

Proceed to the scientific pilot gate. Do not launch a final scientific run.
