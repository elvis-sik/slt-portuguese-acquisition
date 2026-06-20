Read `AGENTS.md` and the SLT complications document. Confirm final behavior trajectories and checkpoint-selection rules are frozen. Execute the LLC campaign in scientific-priority order using one globally selected sampler configuration. Save raw chain traces, running estimates, displacement, timing, and failures. Reject invalid checkpoints explicitly.

Do not retune every checkpoint. Do not call a formal phase transition. Stop optional work before compromising controls or diagnostics. Update state, registry, and the real report-source tables.


---
## Orchestrator directive for this tick
- Time budget: 5.500 wall-clock hours (launch bounded jobs with --max-hours within this; poll and kill as you judge best).
- Task: Run the LLC campaign for final run `final_training_20260620T053855Z` using the frozen behavior-only checkpoint selection in `results/02_final_training/final_training_20260620T053855Z/llc_checkpoint_selection.json` with selected tokens `[0, 100000, 400000, 1500000, 5000000, 8000000]`. Use one globally selected sampler configuration, fixed reference set/loss/sequence length/normalization, and preserve chain-level traces, running estimates, sampler settings, and failures under `results/03_llc_campaign/<run_id>/`. Launch GPU work through `infra/remote/run_bounded_job.sh`. Success criterion: reportable LLC diagnostics exist for the frozen subset, checkpoint selection is unchanged, and `state/current_status.json`, `state/decision_log.md`, and `state/experiment_registry.csv` are updated with a gate decision and next bounded action.
