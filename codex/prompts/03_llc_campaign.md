Read `AGENTS.md` and the SLT complications document. Confirm final behavior trajectories and checkpoint-selection rules are frozen. Execute the LLC campaign in scientific-priority order using one globally selected sampler configuration. Save raw chain traces, running estimates, displacement, timing, and failures. Reject invalid checkpoints explicitly.

Do not retune every checkpoint. Do not call a formal phase transition. Stop optional work before compromising controls or diagnostics. Update state, registry, and the real report-source tables.

Apply the scientific validity gate (`AGENTS.md`): the LLC must be physically valid (positive; sampler not drifting persistently below the checkpoint center). If most checkpoints yield negative/non-physical LLC, the upstream training did not converge — do NOT report negative LLC as a geometric result. Return `status: blocked`, `gate_decision: pivot`, and flag the training as the thing to fix.
