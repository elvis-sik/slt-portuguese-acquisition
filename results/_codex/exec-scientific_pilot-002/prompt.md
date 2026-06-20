Read `AGENTS.md` and `docs/01_RESEARCH_PROTOCOL.md`. Confirm the infrastructure gate passed. Implement and run only the TinyStories-3M scientific pilot within the time budget the orchestrator granted for this tick.

Build immutable small data splits, structured/shuffled conditions, BPB, grammar-margin evaluation, English retention, checkpointing, and manifests. Run the predeclared short LR pilot and early/middle/late sampler cross-check. Launch long commands through the bounded runner. Preserve failures and chain traces. Update state and registry files.

Do not add Spanish or broad localization. Do not proceed to 8M until the pilot gates in `AGENTS.md` are demonstrably satisfied and recorded as a structured gate decision. Under unattended orchestration, the operator's pre-authorization (see "Unattended autonomous operation" in `AGENTS.md`) stands in for per-run human approval, bounded by the hard budget cap and the wall-clock deadline.


---
## Orchestrator directive for this tick
- Time budget: 1.250 wall-clock hours (launch bounded jobs with --max-hours within this; poll and kill as you judge best).
- Task: Start the scientific pilot gate now that infrastructure is passed. Run the bounded pilot on the small English-trained causal LM with the minimum real conditions: structured Portuguese, token-shuffled Portuguese, and matched English, plus the known-good Portuguese baseline or constructed sanity checks for the grammar probe. Use full-parameter continued pretraining, fixed data splits and hashes, fixed evaluation across all saved pilot checkpoints, and one common predeclared sampler configuration for early/middle/late LLC traces. Preserve manifests/logs/status/final exit codes and update state/current_status.json, state/decision_log.md, state/experiment_registry.csv, and a pilot phase report. Success criterion: Portuguese validation improves, grammar probe is above chance or sanity checks pass, structured vs shuffled Portuguese are behaviorally distinguishable in the pilot, early/middle/late sampler traces are interpretable under the same sampler config, and the gate decision is explicitly recorded as proceed, pivot, or fail with evidence paths.
