# Copy-paste prompt for the first Codex thread

> Status, 2026-06-21: historical bootstrap prompt. It is retained to document how the project started,
> not as current execution guidance.

Read `AGENTS.md`, `START_HERE_FOR_CODEX.md`, `docs/00_EXECUTIVE_PLAN.md`, `docs/02_SLT_BAYESIAN_COMPLICATIONS.md`, and `docs/04_BENCHMARKS_AND_FERMI_ESTIMATES.md` before acting.

This is a three-day research sprint. The report under `reference/mock_report/` is wholly synthetic and must never be treated as evidence. Begin with the infrastructure gate only. Inspect the repository, initialize Git if needed, verify the GPU/Python/devinterp environment, run the provided training and sampler benchmarks on TinyStories-3M, save all logs and JSON outputs under `results/00_infrastructure_gate/`, update the state files, and calculate the revised runtime/cost estimate. Diagnose and retain failures. Do not start final training, do not provision/resize/delete cloud resources, and do not exceed one incremental GPU-hour in this first phase. End with a proceed/modify/pivot/stop decision and the exact evidence paths.
