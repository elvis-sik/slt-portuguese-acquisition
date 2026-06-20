# Decision log

## 2026-06-20 — initial handoff

Decision: use GCP as the primary worker; install Codex on the remote VM; keep cloud lifecycle local; run TinyStories-3M infrastructure/scientific gates before TinyStories-8M.

Budget: planning median 7 charged GPU-hours; soft review at 10 hours or $35; hard project cap $50.

Scientific scope: two structured Portuguese seeds, one shuffled Portuguese control, one matched English control; behavior at all checkpoints; reduced LLC replication; no Spanish or broad susceptibility scan until core result is complete.

Evidence status: no empirical runs have been completed. The included report is synthetic.

## 2026-06-20 — infrastructure gate completed

Decision: proceed with modifications. The GCP L4 environment can run the TinyStories-3M CUDA check, random-token training throughput benchmarks, and a `devinterp` 2.0.1 sampler smoke test. Do not start the final campaign yet; next bounded action is the real train-save-reload-evaluate-sample loop with a CPU smoke test and immutable toy data fixture.

Evidence:

- CUDA environment: `results/00_infrastructure_gate/environment.json` reports Python 3.11.15, Torch 2.12.0+cu130, CUDA available on NVIDIA L4, 23.69 GB device memory, TinyStories-3M forward/backward on CUDA, and 8,278,400 parameters.
- Training benchmark: `results/00_infrastructure_gate/train_seq64.json` measured 0.0391 s/step and 52,374 tokens/s at seq64 batch32; `results/00_infrastructure_gate/train_seq128.json` measured 0.0751 s/step and 54,562 tokens/s at seq128 batch32.
- Sampler smoke test: `results/00_infrastructure_gate/sampler_smoke.json` completed two chains, 400 approximate chain steps, 56.43 s wall time, 0.1411 s/chain-step estimate, 3.41 GB peak allocated VRAM, and saved raw trace data under `results/00_infrastructure_gate/sampler_smoke.zarr`.
- Revised estimate: `results/00_infrastructure_gate/project_estimate.json` projects 2.12 / 3.53 / 7.06 charged hours and $2.12 / $3.53 / $7.06 raw compute at the $1.00/h planning assumption. Review required: false.
- Bounded-job logs and diagnostics: `results/_jobs/`.

Failures retained:

- `infra-gate-20260620T0138Z`: failed because Ubuntu 22.04 default Python 3.10 could not satisfy `devinterp==2.0.1` through non-yanked `zarr>=3` releases.
- `infra-gate-py311-20260620T0145Z`: failed because `uv venv` did not seed `pip`; the benchmark runner now uses `uv pip freeze`.
- `infra-gate-py311-20260620T0150Z`: training benchmarks completed, but sampler failed because `devinterp.slt.llc.llc()` now requires an `observables` argument.
- `infra-gate-sampler-20260620T0155Z`: sampler failed because the Hugging Face dataset yielded Python lists for observables; the script now sets the dataset format to torch tensors.

Uncertainty and caveats: all benchmark data are random-token smoke tests, not scientific evidence of Portuguese adaptation or LLC behavior. The estimate excludes VM boot/bootstrap/idle time, disk charges, official GCP pricing variance, and human/OpenAI usage costs. The successful sampler used the remote checkout at `18cd0eb` plus the sampler patch committed with this phase update.

Gate decision: proceed, with modifications. Use Python 3.11+ for all runs, keep the patched `devinterp` observable/tensor handling, and require a real pipeline smoke test before paid final training.
