# SLT Portuguese adaptation - synthetic mock submission

**Important:** Every result in this package is fabricated for project planning. None of the numbers, figures, model runs, changepoints, or interventions are empirical evidence.

## Main artifacts

- `slt_portuguese_synthetic_mock_submission.pdf` - six-page mock hackathon report.
- `slt_portuguese_synthetic_mock_submission.docx` - editable version of the report.
- `figures/` - individual publication-style figures, including one Spanish comparison and one sampler diagnostic not all shown in the main report.
- `synthetic_training_trajectories.csv` - seed-level synthetic metrics by checkpoint.
- `synthetic_changepoints.csv` - synthetic LLC and grammar transition estimates.
- `synthetic_condition_summary.csv` - final-checkpoint summary by condition.
- `synthetic_intervention_summary.csv` - synthetic freeze-intervention outcomes.
- `synthetic_metadata.json` - assumed model, training, evaluation, and sampler setup.
- `generate_synthetic_results.py` - deterministic generator for the fake data and figures.

## Submission format used in the mock-up

The Apart event page asks teams to submit a PDF research report documenting their approach, results, and implications. The official AI Safety Colombia hub page gives a 4-8 page target. This mock-up uses six pages:

1. Problem, contribution, abstract, and submission fit.
2. Experimental design, controls, metrics, and sampler diagnostic.
3. Main behavioral trajectories.
4. LLC trajectory and controls.
5. Seed-level alignment and Spanish replication.
6. Localization, intervention, implications, limitations, and reproducibility.

## What the fabricated outcome says

- Portuguese vocabulary learning starts early and smoothly.
- Compositional grammar improves sharply around 3.4M target-language tokens.
- A peak and drop in normalized LLC occurs in the same interval.
- Shuffled Portuguese learns much of the vocabulary but not the grammar and shows no stable LLC breakpoint.
- Spanish replicates the ordering but transitions earlier under the same token budget.
- Freezing the most responsive MLP block delays but does not abolish grammar generalization.
- English validation performance degrades modestly, exposing a real trade-off rather than a cost-free success.

## Recreating the fake figures

From an environment with NumPy, pandas, SciPy, and Matplotlib:

```bash
python generate_synthetic_results.py
```

The generator is deterministic. It exists only to make the mock-up inspectable and editable.

## Sources used for project framing

- Apart Research, Global South AI Safety Hackathon, 2026.
- AI Safety Colombia, Global South AI Safety Hackathon event page, 2026.
- Hoogland et al., *Loss Landscape Degeneracy and Stagewise Development in Transformers*, arXiv:2402.02364.
- Timaeus Research, `devinterp` documentation and source repository.
