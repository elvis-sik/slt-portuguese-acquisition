# AGENTS.md

## Scope

This repository supports a three-day SLT/developmental-interpretability experiment. Favor a narrow, reproducible result over broad but weak coverage.

## Non-negotiable scientific rules

1. Files under `reference/mock_report/` are synthetic. Never cite their numbers as empirical findings, copy their CSV rows into real results, or overwrite them with real output.
2. The primary model is a small English-trained causal LM adapted by full-parameter next-token continued pretraining. LoRA or adapter-only training changes the geometric question and is not the primary protocol.
3. The minimum real conditions are structured Portuguese, token-shuffled Portuguese, and matched English. The preferred replication is a second Portuguese seed. Spanish and component localization are stretch goals.
4. Behavioral evaluation is computed at all saved checkpoints. LLC is measured at a predeclared subset plus at most two adaptively selected checkpoints surrounding a behavioral candidate transition.
5. Use a fixed sampling reference set, loss definition, sequence length, normalization, and one globally selected sampler configuration across checkpoints in a trajectory. Do not tune each checkpoint for a desired result.
6. Preserve all chain-level traces, running estimates, sampler settings, and failures. A scalar LLC without diagnostics is not reportable.
7. Do not call a result a formal SLT phase transition. Preferred wording: “a changepoint in an SLT-derived local geometric estimate aligned with a behavioral transition.”
8. Do not call a result grokking unless training performance becomes strong substantially before held-out generalization and the delayed improvement is demonstrated continuously, not only by thresholded accuracy.
9. A null or smooth result is acceptable. Do not manipulate smoothing, bins, checkpoint selection, or metrics to manufacture abruptness.
10. Keep raw and processed data splits immutable after the pilot. Record hashes.

## Gating

Before the final 8M experiment, all conditions below must pass:

- complete train-save-reload-evaluate-sample loop works on TinyStories-3M;
- GPU environment passes and peak VRAM has at least 25% headroom;
- one common sampler configuration produces interpretable early, middle, and late traces;
- Portuguese validation improves;
- grammar probe is above chance on a known-good Portuguese baseline or passes constructed sanity checks;
- shuffled Portuguese and structured Portuguese are behaviorally distinguishable in the pilot;
- revised median charged runtime is at most 10 hours and planned spend before contingency is at most $35.

If a gate fails, execute the relevant pivot in `docs/11_FAILURE_MODES_AND_PIVOTS.md` rather than silently weakening the standard.

## Cloud and spending rules

- Cloud lifecycle is controlled from `infra/gcp/` on the operator machine. Do not provision, resize, stop, or delete instances from the GPU worker.
- The worker should have no broad GCP service-account permissions.
- Every job longer than five minutes must be launched through `infra/remote/run_bounded_job.sh` with a maximum runtime.
- Every GPU job writes a manifest, log, status file, and final exit code.
- Do not start an incremental action estimated above two GPU-hours or $5 without recording a gate decision. Do not exceed the repository hard budget without explicit human approval.
- Do not run final jobs on Spot/preemptible capacity unless the operator explicitly changes the plan.

## Engineering rules

- Work in Git. Commit before a long run and record the commit in each manifest.
- Prefer deterministic, restartable commands and config files over notebook-only state.
- New experiment code must have a CPU smoke test or tiny fixture.
- Store generated outputs under `results/<phase>/<run_id>/`; do not place results in source directories.
- Record seeds, data order, tokenizer hash, package versions, hardware, precision, optimizer state, checkpoint hashes, and cumulative bytes/tokens.
- Avoid deleting failed runs. Mark them failed and retain diagnostic artifacts.
- Do not depend on the internet during a final run after models/data are cached.
- Use FP32 for initial SGLD. Training may move to BF16 only after a benchmark and an explicit comparison.

## Phase completion format

Update these files after every phase:

- `state/current_status.json`
- `state/decision_log.md`
- `state/experiment_registry.csv`

A phase report must state: evidence, uncertainty, failure modes, runtime, cost projection, gate decision, and next bounded action.
