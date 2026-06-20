# Diagnose and fix

The previous execution step failed or was blocked. Your job is to make the smallest, well-tested
change that unblocks progress — not to push the science forward this tick.

Read `AGENTS.md` first. Then:

1. Read the most recent failure: the last entry in `state/decision_log.md`, the failing run under
   `results/_jobs/<name>/` (`stdout_stderr.log`, `exit_code`, `status`), and the harness-provided
   `task_instruction` describing what was attempted.
2. Form a specific hypothesis for the root cause. Prefer environment/config/data-shape causes
   (the kinds already seen in the infrastructure gate: Python version, missing pip, library API
   drift, tensor formats) before assuming a deep bug.
3. Apply the minimal fix. Add or update a CPU smoke test / tiny fixture that reproduces the failure
   and now passes (AGENTS.md engineering rule).
4. Do NOT launch a long GPU job here. Validate with the smoke test or a very short bounded job only.
5. Preserve the failed run's artifacts; never delete them. Record what failed and what you changed.
6. Update `state/decision_log.md` and `state/experiment_registry.csv`.

Return a `run_decision` (matching `codex/schemas/run_decision.schema.json`). Use
`gate_decision: "proceed"` if the fix is verified and the real stage can be retried next tick,
`modify`/`pivot` if a different approach is now warranted, or `blocked`/`stop` if a human is needed.
Keep `requires_human_approval` false unless the fix needs a decision outside the pre-authorized
autonomy envelope.


---
## Orchestrator directive for this tick
- Time budget: 0.500 wall-clock hours (launch bounded jobs with --max-hours within this; poll and kill as you judge best).
- Task: Diagnose the infrastructure blocker without launching training: inspect the current phase report/state, exact worker shell Python environment, CUDA device nodes, NVIDIA kernel/user-space driver consistency, `nvidia-smi`, `scripts/check_environment.py`, and PyTorch CUDA visibility. If a non-destructive user-level repair is available, such as activating an existing intended venv/conda environment, apply it and rerun only the preflight checks. Do not provision, resize, reboot, stop, delete cloud resources, install system drivers, or run TinyStories/training/sampler jobs. Success criterion: either fresh passing preflight artifacts that justify retrying the infrastructure gate, or updated state/report artifacts identifying a precise unrecoverable operator-side blocker and the minimal operator action needed.
