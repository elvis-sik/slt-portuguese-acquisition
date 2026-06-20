# Recipe Search Attempt Report

- Run ID: `recipe_search_20260620T171838Z_lr1e-4_wiki1m`
- Source commit: `8888d5e19fb3d7d241b54b09d2f1c53eefb67c10`
- Model: `roneneldan/TinyStories-8M`
- Gate decision: `proceed`

## Recipe

- LR: `0.0001`
- Warmup fraction: `0.03`
- Schedule: `cosine`
- Grad clip: `1.0`
- Weight decay: `0.01`
- Batch size: `64`
- Target tokens per condition: `1007616`

## Evidence

- Manifest: `results/recipe_search/recipe_search_20260620T171838Z_lr1e-4_wiki1m/manifest.json`
- Data manifest: `results/recipe_search/recipe_search_20260620T171838Z_lr1e-4_wiki1m/data_splits/split_manifest.json`
- Structured summary: `results/recipe_search/recipe_search_20260620T171838Z_lr1e-4_wiki1m/conditions/structured_pt/condition_summary.json`
- Shuffled summary: `results/recipe_search/recipe_search_20260620T171838Z_lr1e-4_wiki1m/conditions/shuffled_pt/condition_summary.json`
- Structured checkpoint: `results/recipe_search/recipe_search_20260620T171838Z_lr1e-4_wiki1m/conditions/structured_pt/checkpoints/tokens_001000000`

## Metrics

- Structured PT BPB: `6.773542` -> `3.806601` (`-2.966940`)
- Shuffled PT final BPB: `4.214080`
- Structured-vs-shuffled final gap: `0.407478`
- Stable: `True`

## Runtime And Cost

- Wall seconds: `76.08`
- Estimated GPU hours: `0.0211`
- Estimated cost USD: `$0.0211`

## Uncertainty

- This is a recipe-search attempt, not a final scientific result.
- The fixed validation set is the pilot OPUS validation split; training chunks come from a fresh Portuguese Wikipedia stream slice.
- A successful recipe should be continued only after operator greenlight.

## Failure Modes

- A short run can show early adaptation that later degrades; scale-up must continue to monitor BPB.
- Shuffled-control separation can be noisy at small token budgets.

## Next Action

Stop for operator greenlight; continue this recipe from the structured checkpoint to a larger token budget.
