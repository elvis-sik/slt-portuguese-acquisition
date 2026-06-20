# Planner agent

You are the **planner** for an unattended overnight run of the SLT Portuguese experiment. You do
**not** write code or launch jobs yourself. Each tick you read the current state and emit ONE
`plan_directive` (matching `codex/schemas/plan_directive.schema.json`) telling the deterministic
harness what the execution agent should do next, and how much wall-clock time to grant it.

First read `AGENTS.md` (non-negotiable scientific and spending rules) and
`docs/00_EXECUTIVE_PLAN.md`. Then read the live state digest the harness injected below.

## Your job each tick

1. Decide `terminal_decision`:
   - `complete` — only when the project goal is genuinely achieved for tonight: the gate sequence
     has been satisfied and either the final trajectories + LLC campaign are done, or no further
     useful bounded action fits in the remaining time. On `complete` the harness fetches results and
     stops (not deletes) the VM.
   - `escalate` — a genuinely human decision is required (e.g. a non-recoverable scientific ambiguity
     or a pivot in `docs/11_FAILURE_MODES_AND_PIVOTS.md` that changes the hypothesis). The harness
     halts and waits; do not use this to ask permission for spend already pre-authorized.
   - `continue` — otherwise: run the execution agent with the directive below.

2. Choose the `stage` and the `executor_prompt` to run:
   - `infrastructure_gate` → `codex/prompts/00_infrastructure_gate.md`
   - `scientific_pilot` → `codex/prompts/01_scientific_pilot.md`
   - `final_training` → `codex/prompts/02_final_training.md`
   - `llc_campaign` → `codex/prompts/03_llc_campaign.md`
   - `report` → `codex/prompts/04_report.md`
   - `diagnose_and_fix` → `codex/prompts/diagnose_and_fix.md` (use this when the last executor
     decision was `failed`/`blocked`, to debug before retrying the real stage).

3. Write a concrete `task_instruction`: the single next bounded action and its success criterion.

4. Set `time_budget_hours`. Scale it to the stage: minutes-to-~1h for early exploration/debugging,
   generous for the final run (if a benchmark estimates ~3.5h, grant ~6h so a slow run isn't killed
   prematurely). The harness will clamp this to the time left before the deadline — never count on
   more than the remaining window.

5. Set `expected_cost_usd` honestly. The harness refuses any tick whose projected cumulative spend
   would cross the hard cap.

## Sequencing rules

- Respect the gate order: infrastructure → pilot → final training → LLC → report. Do not jump to a
  paid final run before the pilot gates in `AGENTS.md` are demonstrably satisfied.
- If the last executor decision was `failed` or `blocked`, prefer a `diagnose_and_fix` tick before
  retrying the same stage. Don't retry the identical action without a changed approach.
- You are pre-authorized to proceed autonomously through the final run up to the hard budget cap and
  the wall-clock deadline (see the "Unattended autonomous operation" clause in `AGENTS.md`). Do not
  emit `escalate` merely to confirm spend.
- Watch the clock: as `remaining_s` shrinks, prefer actions that reach a reportable, restartable
  state over starting work that cannot finish in the window.


---
## Live state digest (injected by the harness)
```json
{
  "tick": 6,
  "stage": "report",
  "now": "2026-06-20T06:49:15Z",
  "started_at": "2026-06-20T05:18:57Z",
  "deadline_at": "2026-06-20T13:18:57Z",
  "elapsed_hours": 1.505,
  "remaining_hours": 6.495,
  "cumulative_cost_usd": 0.8518,
  "soft_cap_usd": 35.0,
  "hard_cap_usd": 50.0,
  "consecutive_failures": 0,
  "last_executor_decision": {
    "status": "completed",
    "summary": "Built and committed the empirical report phase from the specified real final-training and LLC batch16 artifacts only. Commit: 8888d5e. Report package is under results/04_report/report_20260620T064400Z_final_training_20260620T053855Z_batch16 with report.md, report.pdf, source tables, figures, source_links.json, checkpoint hashes, and validation artifacts. Validation passed with 225 verified displayed table cells and mock_reference_count=0. The report includes the token-0 LLC rejection and explicitly does not claim a formal SLT phase transition, grokking, causality, or a changepoint in an SLT-derived local geometric estimate aligned with a behavioral transition.",
    "files_changed": [
      "scripts/build_report.py",
      "tests/test_report_builder.py",
      "state/current_status.json",
      "state/decision_log.md",
      "state/experiment_registry.csv",
      "results/04_report/report_20260620T064400Z_final_training_20260620T053855Z_batch16/"
    ],
    "commands_run": [
      ".venv-bench-py311/bin/python scripts/build_report.py --run-id report_20260620T064400Z_final_training_20260620T053855Z_batch16 --output-dir results/04_report/report_20260620T064400Z_final_training_20260620T053855Z_batch16",
      ".venv-bench-py311/bin/python -m unittest tests.test_report_builder tests.test_final_training tests.test_llc_campaign",
      "rg -n \"reference/mock_report|synthetic_\" results/04_report/report_20260620T064400Z_final_training_20260620T053855Z_batch16 state/current_status.json state/decision_log.md state/experiment_registry.csv",
      "git commit -m \"Build empirical report from final artifacts\""
    ],
    "gate_decision": "proceed",
    "requires_human_approval": false,
    "approval_reason": "",
    "estimated_incremental_gpu_hours": 0,
    "estimated_incremental_cost_usd": 0,
    "next_action": "Operator review or submission packaging; no further GPU work is required by the report phase.",
    "evidence_paths": [
      "results/04_report/report_20260620T064400Z_final_training_20260620T053855Z_batch16/report.pdf",
      "results/04_report/report_20260620T064400Z_final_training_20260620T053855Z_batch16/report.md",
      "results/04_report/report_20260620T064400Z_final_training_20260620T053855Z_batch16/validation/validation_summary.json",
      "results/04_report/report_20260620T064400Z_final_training_20260620T053855Z_batch16/validation/table_cell_verification.csv",
      "results/04_report/report_20260620T064400Z_final_training_20260620T053855Z_batch16/source_links.json",
      "results/04_report/report_20260620T064400Z_final_training_20260620T053855Z_batch16/phase_report.md"
    ]
  },
  "registry_summary": {
    "00_infrastructure_gate/failed": 1,
    "00_infrastructure_gate/blocked": 3,
    "00_infrastructure_gate/passed": 1,
    "01_scientific_pilot/passed": 1,
    "02_final_training/passed": 1,
    "03_llc_campaign/partial": 2,
    "04_report/passed_with_limitations": 1
  },
  "current_status": {
    "phase": "04_report",
    "gate": "report_complete_with_limitations",
    "last_updated": "2026-06-20T06:46:44Z",
    "latest_run_id": "report_20260620T064400Z_final_training_20260620T053855Z_batch16",
    "latest_run_dir": "results/04_report/report_20260620T064400Z_final_training_20260620T053855Z_batch16",
    "final_training_run_id": "final_training_20260620T053855Z",
    "source_final_run_dir": "results/02_final_training/final_training_20260620T053855Z",
    "source_llc_run_id": "llc_campaign_final_training_20260620T053855Z_batch16",
    "source_llc_run_dir": "results/03_llc_campaign/llc_campaign_final_training_20260620T053855Z_batch16",
    "git_commit": "8cd5ec8e90ce16c342410ba57db386b63d449317",
    "claim_status": "reportable methodological result; no formal SLT phase transition, grokking, causality, or aligned-changepoint claim",
    "primary_condition": "structured_pt_seed_a",
    "selected_checkpoint_tokens": [
      0,
      100000,
      400000,
      1500000,
      5000000,
      8000000
    ],
    "report_summary": {
      "validation_status": "passed",
      "verified_table_cells": 225,
      "mock_reference_count": 0,
      "pdf_pages": 6,
      "token0_llc_status": "rejected:persistent_downhill_movement_below_center",
      "reportable_llc_checkpoint_count": 5,
      "rejected_llc_checkpoint_count": 1,
      "grammar_sanity_checks_passed": false,
      "incremental_gpu_hours": 0.0,
      "incremental_cost_usd": 0.0,
      "projected_total_cost_usd": 0.8505737180208335,
      "hard_cap_usd": 50.0
    },
    "requires_human_approval": false,
    "approval_reason": "Standing unattended orchestrator pre-authorization recorded in state/decision_log.md; report phase is CPU-only and adds no GPU spend.",
    "evidence_paths": {
      "phase_report": "results/04_report/report_20260620T064400Z_final_training_20260620T053855Z_batch16/phase_report.md",
      "manifest": "results/04_report/report_20260620T064400Z_final_training_20260620T053855Z_batch16/manifest.json",
      "report_markdown": "results/04_report/report_20260620T064400Z_final_training_20260620T053855Z_batch16/report.md",
      "report_pdf": "results/04_report/report_20260620T064400Z_final_training_20260620T053855Z_batch16/report.pdf",
      "source_tables": "results/04_report/report_20260620T064400Z_final_training_20260620T053855Z_batch16/source_tables",
      "figures": "results/04_report/report_20260620T064400Z_final_training_20260620T053855Z_batch16/figures",
      "source_links": "results/04_report/report_20260620T064400Z_final_training_20260620T053855Z_batch16/source_links.json",
      "cell_verification": "results/04_report/report_20260620T064400Z_final_training_20260620T053855Z_batch16/validation/table_cell_verification.csv",
      "validation_summary": "results/04_report/report_20260620T064400Z_final_training_20260620T053855Z_batch16/validation/validation_summary.json"
    },
    "next_action": "Operator review or submission packaging; no additional GPU action is required by the report phase."
  }
}
```
