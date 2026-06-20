Read `AGENTS.md`, `START_HERE_FOR_CODEX.md`, and the benchmark/Fermi document. Complete only the infrastructure gate. Do not launch a final scientific run.

Inspect the environment, initialize/commit the repository if needed, run the 3M model check, training benchmarks at sequence lengths 64 and 128, and the short devinterp sampler smoke test. Save all logs and JSONs under `results/00_infrastructure_gate/`. Diagnose failures rather than hiding them. Update the state files and recalculate project runtime/cost. If a command could exceed one GPU-hour, do not launch it in this phase.

Return a structured gate decision. Human approval is required before any paid final campaign.
