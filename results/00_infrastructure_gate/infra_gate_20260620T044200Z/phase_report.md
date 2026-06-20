# Infrastructure Gate Report

Run ID: `infra_gate_20260620T044200Z`
Git HEAD: `18cd0ebe6529a6b5fddcecad42eef2e6805cb0e5`
Decision: `pivot`

## Evidence

- `environment.json`: TinyStories-3M loaded from cache with 8,278,400 trainable parameters and completed a CPU forward/backward pass, but `nvidia-smi` returned exit status 9, `torch_cuda_available` was false, and CUDA device count was 0.
- `nvidia_smi_live.txt`: live NVIDIA driver check failed: "couldn't communicate with the NVIDIA driver."
- `jobs/train-seq64/stdout_stderr.log`: training benchmark failed with `RuntimeError: CUDA is required for the intended cloud benchmark`.
- `jobs/train-seq128/stdout_stderr.log`: training benchmark failed with `RuntimeError: CUDA is required for the intended cloud benchmark`.
- `jobs/sampler-smoke/stdout_stderr.log`: sampler smoke failed with `RuntimeError: CUDA is required for the intended cloud sampler benchmark`.
- `gate_summary.json`: structured summary of the failed gate and applicable pivot.

## Commands

All gate commands were launched through `infra/remote/run_bounded_job.sh`. In this Codex sandbox, detached jobs did not survive after the launcher command exited, so the generated `runner.sh` files were executed in the foreground to populate each job's log, status, end time, and exit code.

```bash
JOB_ROOT=results/00_infrastructure_gate/infra_gate_20260620T044200Z/jobs \
  infra/remote/run_bounded_job.sh --name check-env-offline --max-hours 0.05 --auto-stop-vm no -- \
  env HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  .venv-bench-py311/bin/python scripts/check_environment.py \
  --model roneneldan/TinyStories-3M \
  --output results/00_infrastructure_gate/infra_gate_20260620T044200Z/environment.json

JOB_ROOT=results/00_infrastructure_gate/infra_gate_20260620T044200Z/jobs \
  infra/remote/run_bounded_job.sh --name train-seq64 --max-hours 0.08 --auto-stop-vm no -- \
  env HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  .venv-bench-py311/bin/python scripts/benchmark_train.py \
  --model roneneldan/TinyStories-3M --sequence-length 64 --batch-size 32 \
  --warmup-steps 50 --steps 200 \
  --output results/00_infrastructure_gate/infra_gate_20260620T044200Z/train_seq64.json

JOB_ROOT=results/00_infrastructure_gate/infra_gate_20260620T044200Z/jobs \
  infra/remote/run_bounded_job.sh --name train-seq128 --max-hours 0.08 --auto-stop-vm no -- \
  env HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  .venv-bench-py311/bin/python scripts/benchmark_train.py \
  --model roneneldan/TinyStories-3M --sequence-length 128 --batch-size 32 \
  --warmup-steps 50 --steps 200 \
  --output results/00_infrastructure_gate/infra_gate_20260620T044200Z/train_seq128.json

JOB_ROOT=results/00_infrastructure_gate/infra_gate_20260620T044200Z/jobs \
  infra/remote/run_bounded_job.sh --name sampler-smoke --max-hours 0.08 --auto-stop-vm no -- \
  env HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  .venv-bench-py311/bin/python scripts/benchmark_sampler.py \
  --model roneneldan/TinyStories-3M --sequence-length 128 --batch-size 32 \
  --num-chains 2 --num-burnin-steps 100 --num-draws 50 --num-steps-between-draws 2 \
  --output results/00_infrastructure_gate/infra_gate_20260620T044200Z/sampler_smoke.json
```

## Uncertainty

The model cache appears usable because the 3M checkpoint loads offline. Current GPU performance, current peak VRAM, and current sampler trace validity are not measurable while CUDA is unavailable. Prior successful benchmark artifacts under `results/00_infrastructure_gate/` show adequate VRAM headroom and a 3.53 hour planning median, but those are stale and do not make this live gate pass.

## Failure Mode

Applicable pivot: `docs/11_FAILURE_MODES_AND_PIVOTS.md` -> GPU driver or PyTorch CUDA failure. Repair or restart the driver from the operator side, verify `nvidia-smi`, then verify PyTorch CUDA before reinstalling Python packages.

## Runtime And Cost

Current-run benchmark cost is not reportable because no CUDA device was visible. The bounded attempts consumed only short wall-clock time; a conservative planning charge of 0.05 GPU-hours / $0.05 is recorded.

Recalculation from the most recent successful benchmark JSONs:

- Median charged runtime: 3.53 hours
- Median cost at $1/h: $3.53
- High estimate: 7.06 hours
- Review required by estimate: false

## Gate Decision

`pivot`: Do not proceed to the scientific pilot or final run. The next bounded action is operator-side driver repair or VM stop/restart, followed by rerunning only the infrastructure gate until live CUDA, seq64/seq128 benchmarks, sampler smoke, train-save-reload-evaluate-sample loop, and VRAM headroom all pass.
