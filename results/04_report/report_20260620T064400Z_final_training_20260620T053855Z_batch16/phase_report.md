# Report Phase Report

- Run ID: `report_20260620T064400Z_final_training_20260620T053855Z_batch16`
- Generated UTC: `2026-06-20T06:46:41Z`
- Source final run: `results/02_final_training/final_training_20260620T053855Z`
- Source LLC run: `results/03_llc_campaign/llc_campaign_final_training_20260620T053855Z_batch16`
- Gate decision: `report_complete_with_limitations`

## Evidence

- Report Markdown: `results/04_report/report_20260620T064400Z_final_training_20260620T053855Z_batch16/report.md`
- Report PDF: `results/04_report/report_20260620T064400Z_final_training_20260620T053855Z_batch16/report.pdf`
- Source tables: `results/04_report/report_20260620T064400Z_final_training_20260620T053855Z_batch16/source_tables`
- Figures: `results/04_report/report_20260620T064400Z_final_training_20260620T053855Z_batch16/figures`
- Cell verification: `results/04_report/report_20260620T064400Z_final_training_20260620T053855Z_batch16/validation/table_cell_verification.csv`
- Validation summary: `results/04_report/report_20260620T064400Z_final_training_20260620T053855Z_batch16/validation/validation_summary.json`
- Source links: `results/04_report/report_20260620T064400Z_final_training_20260620T053855Z_batch16/source_links.json`

## Uncertainty

- No LLC controls were run for shuffled Portuguese, matched English, or structured Portuguese seed B.
- The token-0 LLC scalar is rejected for `persistent_downhill_movement_below_center`.
- Grammar margins use 10 constructed pairs, and the grammar sanity check file has `passed=false`.
- Checkpoint spacing limits transition localization.
- The smooth/null alternative remains plausible.

## Failure Modes

- Scalar LLC without diagnostics is not reportable; diagnostics and trace paths are retained.
- The result is conditional on the fixed sampler reference set and one global sampler configuration.
- The report does not claim a formal SLT phase transition, grokking, causality, or a changepoint in an SLT-derived local geometric estimate aligned with a behavioral transition.

## Runtime And Cost

Report construction used CPU-only local processing. Incremental GPU-hours: `0.0000`; incremental cost: `$0.0000`.
The source final training and LLC campaign runtime/cost are reported in `source_tables/runtime_cost_gates.csv`.

## Validation

- Validation status: `passed`
- Verified table cells: `225`
- Synthetic/mock references in report artifacts: `0`

## Gate Decision

`report_complete_with_limitations`. Next bounded action: operator review/submission packaging if desired; no additional GPU action is required by this report phase.
