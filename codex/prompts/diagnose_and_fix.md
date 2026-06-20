# Diagnose and fix

The previous execution step failed or was blocked. Your job is to make the smallest, well-tested
change that unblocks progress — not to push the science forward this tick.

Read `AGENTS.md` first. Then:

1. Read the most recent failure: the last entry in `state/decision_log.md`, the failing run under
   `results/_jobs/<name>/` (`stdout_stderr.log`, `exit_code`, `status`), and the harness-provided
   `task_instruction` describing what was attempted.
2. Form a specific hypothesis for the root cause. Prefer environment/config/data-shape causes
   (the kinds already seen in the infrastructure gate: Python version, missing pip, library API
   drift, tensor formats) before assuming a deep bug. **If the failure is a scientific-validity
   failure** (structured-PT BPB increasing instead of decreasing; the model degrading; negative /
   non-physical LLC), the root cause is usually training configuration: learning rate too high,
   missing warmup / LR decay, no gradient clipping, token budget far too small to learn the target,
   wrong scale, or a tokenization/eval mismatch. Diagnose those.
3. Apply the minimal fix. Add or update a CPU smoke test / tiny fixture that reproduces the failure
   and now passes (AGENTS.md engineering rule).
4. Keep GPU work short. Prefer the smoke test or a very short bounded job. For a training-config fix,
   a single short bounded training run (a few minutes) to confirm the loss now moves the right
   direction is allowed within the time budget; do not launch a full campaign here.
5. Preserve the failed run's artifacts; never delete them. Record what failed and what you changed.
6. Update `state/decision_log.md` and `state/experiment_registry.csv`.

Return a `run_decision` (matching `codex/schemas/run_decision.schema.json`). Use
`gate_decision: "proceed"` if the fix is verified and the real stage can be retried next tick,
`modify`/`pivot` if a different approach is now warranted, or `blocked`/`stop` if a human is needed.
Keep `requires_human_approval` false unless the fix needs a decision outside the pre-authorized
autonomy envelope.
