# Start here for Codex

> Status, 2026-06-21: historical handoff document. The project has already run; use `README.md`,
> `PROJECT_STATUS.md`, and the reports under `reports/` for the current submission state.

You are taking over a time-constrained experimental research project. Read `AGENTS.md` in full before changing files or launching jobs.

## Mission

Test whether a small English-trained causal language model shows an SLT-informed geometric changepoint while it acquires Portuguese through full-parameter continued pretraining, and whether that geometric change aligns with compositional grammatical generalization rather than only vocabulary exposure.

## First task

Do not begin the final experiment. Complete the infrastructure gate:

1. Inspect repository status and create a Git commit before substantive changes.
2. Run `python scripts/check_environment.py --model roneneldan/TinyStories-3M`.
3. Run the training benchmark at sequence lengths 64 and 128.
4. Run a short `devinterp` sampler smoke test on one checkpoint.
5. Store all outputs under `results/00_infrastructure_gate/`.
6. Update `state/decision_log.md`, `state/experiment_registry.csv`, and `state/current_status.json`.
7. Calculate the revised project runtime and cost with `scripts/estimate_project.py`.
8. Stop and request human approval if the revised median exceeds 10 charged GPU-hours or $35 before contingency.

## Scientific boundaries

- The mock report is not evidence and must remain isolated under `reference/mock_report/`.
- Do not describe an empirical result as grokking or a formal Bayesian phase transition without satisfying the claim rules in the protocol.
- Do not use LoRA for the primary experiment.
- Do not optimize sampler settings independently at every checkpoint.
- Do not choose checkpoints solely after inspecting LLC.
- Preserve every sampler trace, including failures.
- Full-parameter training and raw checkpoint export are required for the primary experiment.

## Operational boundaries

- Never create, resize, or delete cloud resources from inside the remote worker.
- Never increase the planned charged GPU budget without a human gate.
- Long jobs must use `infra/remote/run_bounded_job.sh` with a runtime limit.
- Stop on NaNs, repeated OOMs, invalid sampler traces, missing checkpoints, or cost/time threshold violations.
- The remote VM should not hold broad GCP IAM credentials.

## Expected handoff output after each phase

Create a phase report containing:

- exact commands and Git commit;
- machine/GPU/software metadata;
- run manifests and checkpoint hashes;
- runtime and projected dollar cost;
- figures, including negative diagnostics;
- gate decision: proceed, modify, pivot, or stop;
- next bounded action and its incremental budget.
