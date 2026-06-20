# Scientific Pilot Phase Report

- Run ID: `scientific_pilot_20260620T053047Z`
- Source commit: `5c3cd8e493b0d9c9a0be0b748e8b66e3eadbed44`
- Model: `roneneldan/TinyStories-3M`
- Conditions: `structured_pt, shuffled_pt, matched_en`
- Gate decision: `proceed`

## Evidence

- data_manifest: `results/01_scientific_pilot/scientific_pilot_20260620T053047Z/data_splits/split_manifest.json`
- lr_pilot: `results/01_scientific_pilot/scientific_pilot_20260620T053047Z/lr_pilot/lr_pilot_summary.json`
- structured_summary: `results/01_scientific_pilot/scientific_pilot_20260620T053047Z/conditions/structured_pt/condition_summary.json`
- shuffled_summary: `results/01_scientific_pilot/scientific_pilot_20260620T053047Z/conditions/shuffled_pt/condition_summary.json`
- matched_english_summary: `results/01_scientific_pilot/scientific_pilot_20260620T053047Z/conditions/matched_en/condition_summary.json`
- llc_cross_check: `results/01_scientific_pilot/scientific_pilot_20260620T053047Z/llc_cross_check/llc_cross_check_summary.json`
- grammar_sanity: `results/01_scientific_pilot/scientific_pilot_20260620T053047Z/grammar_sanity_checks.json`

## Key Metrics

- structured_pt_initial_bpb: `6.453182046339674`
- structured_pt_final_bpb: `4.149824143996355`
- structured_pt_bpb_delta: `-2.3033579023433193`
- shuffled_pt_final_bpb: `4.351110263827179`
- structured_vs_shuffled_pt_bpb_gap: `0.201286119830824`
- matched_english_initial_bpb: `2.6943750109081397`
- matched_english_final_bpb: `2.77616520472524`
- matched_english_bpb_delta: `0.0817901938171004`
- structured_final_grammar_accuracy: `0.8`
- structured_final_grammar_mean_margin: `0.5566272735595703`
- estimated_gpu_hours: `0.012496694496388853`
- estimated_cost_usd: `0.012496694496388853`
- selected_learning_rate: `0.0003`

## Criteria

- portuguese_validation_improves: `True`
- grammar_probe_above_chance_or_sanity_passes: `True`
- structured_vs_shuffled_behaviorally_distinguishable: `True`
- common_sampler_interpretable_early_middle_late: `True`
- runtime_projection_within_gate: `True`
- infrastructure_gate_confirmed_before_pilot: `True`
- minimum_conditions_completed: `True`

## Uncertainty

- This is a short TinyStories-3M pilot, not the final 8M trajectory.
- Grammar probe pass may rely on constructed sanity checks if TinyStories-3M is not a known-good Portuguese baseline.
- LLC traces are early/middle/late pilot diagnostics under one fixed config, not a formal phase-transition claim.

## Failure Modes

- Small OPUS stream prefix may not represent the final corpus distribution.
- Very short training can make structured-control separation noisy.
- Sampler diagnostics are intentionally shallow under the tick time budget.

## Runtime And Cost

- Wall seconds: `44.99`
- Estimated GPU hours: `0.0125`
- Estimated cost USD: `$0.0125`

## Gate Decision

`proceed`. Record pilot pass, then ask the planner for the next bounded gate; do not launch TinyStories-8M in this tick.
