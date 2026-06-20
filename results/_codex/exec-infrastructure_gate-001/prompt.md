Read `AGENTS.md`, `START_HERE_FOR_CODEX.md`, and the benchmark/Fermi document. Complete only the infrastructure gate. Do not launch a final scientific run.

Inspect the environment, initialize/commit the repository if needed, run the 3M model check, training benchmarks at sequence lengths 64 and 128, and the short devinterp sampler smoke test. Save all logs and JSONs under `results/00_infrastructure_gate/`. Diagnose failures rather than hiding them. Update the state files and recalculate project runtime/cost. Keep each launched command within the time budget the orchestrator granted for this tick.

Return a structured gate decision. Under unattended orchestration, the operator's pre-authorization (see "Unattended autonomous operation" in `AGENTS.md`) stands in for per-run human approval, bounded by the hard budget cap and the wall-clock deadline.


---
## Orchestrator directive for this tick
- Time budget: 1.250 wall-clock hours (launch bounded jobs with --max-hours within this; poll and kill as you judge best).
- Task: Run the infrastructure gate fresh on the now-GPU-accessible VM. Verify CUDA visibility, record GPU model and peak VRAM/headroom, run the complete train-save-reload-evaluate-sample loop on TinyStories-3M, and use infra/remote/run_bounded_job.sh for any job over five minutes. Preserve manifests, logs, status files, final exit codes, and the current git commit. Update state/current_status.json, state/decision_log.md, and state/experiment_registry.csv with evidence, uncertainty, runtime, cost projection, gate decision, and next bounded action. Success criterion: infrastructure gate is passed/ready_for_pilot with at least 25% VRAM headroom and no reliance on prior failed CUDA history.
