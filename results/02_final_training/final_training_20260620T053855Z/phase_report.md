# Final Behavioral Training Phase Report

- Run ID: `final_training_20260620T053855Z`
- Source commit: `98913e931d2dd1ea4453a519b2ff860008cffb69`
- Model: `roneneldan/TinyStories-8M`
- Conditions: `structured_pt_seed_a, shuffled_pt, matched_en, structured_pt_seed_b`
- Gate decision: `proceed_to_llc`

## Evidence

- Manifest: `results/02_final_training/final_training_20260620T053855Z/manifest.json`
- Frozen config: `results/02_final_training/final_training_20260620T053855Z/frozen_config.json`
- Final data manifest: `results/02_final_training/final_training_20260620T053855Z/data_splits/split_manifest.json`
- Cost projection: `results/02_final_training/final_training_20260620T053855Z/cost_projection.json`
- LLC checkpoint selection: `results/02_final_training/final_training_20260620T053855Z/llc_checkpoint_selection.json`
- structured_pt_seed_a summary: `results/02_final_training/final_training_20260620T053855Z/conditions/structured_pt_seed_a/condition_summary.json`
- shuffled_pt summary: `results/02_final_training/final_training_20260620T053855Z/conditions/shuffled_pt/condition_summary.json`
- matched_en summary: `results/02_final_training/final_training_20260620T053855Z/conditions/matched_en/condition_summary.json`
- structured_pt_seed_b summary: `results/02_final_training/final_training_20260620T053855Z/conditions/structured_pt_seed_b/condition_summary.json`

## Behavioral Metrics

- structured_pt_seed_a: final PT BPB `6.26152273889785`, English BPB `4.392169948267166`, grammar mean margin `1.9165000915527344`
- shuffled_pt: final PT BPB `8.057754561969649`, English BPB `5.145446840108829`, grammar mean margin `1.1275129318237305`
- matched_en: final PT BPB `8.793502745949624`, English BPB `3.865956703291504`, grammar mean margin `-2.6043817520141603`
- structured_pt_seed_b: final PT BPB `6.497978548528638`, English BPB `4.71169870564391`, grammar mean margin `3.016176223754883`

## LLC Selection

- Fixed tokens: `[0, 100000, 400000, 1500000, 8000000]`
- Adaptive bracket tokens: `[5000000, 8000000]`
- Selected tokens: `[0, 100000, 400000, 1500000, 5000000, 8000000]`
- Final LLC inspected: `False`

## Runtime And Cost

- Observed phase GPU-hours: `0.1425`
- Projected phase GPU-hours: `0.1425`
- Projected total cost USD: `$0.2469`
- Hard cap USD: `$50.00`

## Uncertainty

- The final training data reuses the immutable pilot split artifacts and cycles them to the target-token budget.
- Behavior checkpoint spacing limits transition localization to adjacent saved checkpoints.
- No final LLC traces were inspected or optimized during this phase.

## Failure Modes

- Repeated small split examples can overfit; report train/eval split hashes and treat this as a narrow final trajectory.
- Checkpoint serialization dominates wall time more than the synthetic throughput benchmark suggests.
- If the next LLC campaign finds unstable localized chains, report diagnostics rather than a scalar-only estimate.

## Gate Decision

`proceed_to_llc`. Behavior outputs and checkpoint-selection rules are frozen.
