# Hackathon submission guide

_Status, 2026-07-05: historical submission guide. The hackathon is over; the GitHub repository is the
archived supporting code/data-summary link._

The public Apart event page asks for a research report documenting approach, results, and implications.
The event welcomes technical-safety work on Portuguese- and Spanish-language models. The current
submission should point reviewers to the Google Doc for the polished report and to this repository for
code, benchmark construction, compact result summaries, and provenance.

## Recommended six-page structure

| Page | Content |
|---|---|
| 1 | question, abstract, one headline result, regional/safety relevance |
| 2 | model, data, controls, hypotheses, metrics, sampler protocol |
| 3 | main behavioral trajectories |
| 4 | LLC trajectory, controls, and final outcomes |
| 5 | seed/checkpoint alignment and optional replication |
| 6 | intervention if available, implications, limitations, reproducibility |

## What a strong submission looks like

- one narrow contribution that is understandable in the abstract;
- a real artifact or experiment rather than only a proposal;
- meaningful controls, not merely more model variants;
- seed/checkpoint uncertainty and negative diagnostics;
- explicit evidence that sampler settings were not selected post hoc per checkpoint;
- clear distinction between association and causality;
- reproducible code/config/data construction;
- a concrete Portuguese-language safety or evaluation implication;
- limitations prominent enough that a reviewer can trust the positive claim.

## Current result package

- shared Google Doc report;
- GitHub repository/commit;
- exact evaluation items and generator/scorer under `data/eval/` and `scripts/`;
- current narrative summaries in `PROJECT_STATUS.md`, `reports/seed_a_llc_trajectory/REPORT.md`, and
  `reports/control_comparison/REPORT.md`;
- compact machine-readable summaries under `results/02_final_training/` and `results/03_llc_campaign/`;
- hashes, frozen configs, and manifests where they are small enough to keep in Git;
- `REPRODUCE.md`, which separates Git-only checks from full GPU/checkpoint reruns;
- `FUTURE_WORK.md`, which collects the remaining research ideas;
- clear limitations: one Portuguese seed, controls and localization check done, seed replication future work.

Do not submit or link stale local exports as if they are final. The old TeX/PDF draft and the earlier 8M
diagnostic report package were removed from the tracked tree.

## Reporting language

Preferred:

> We found an LLC changepoint in the same checkpoint interval as a rise in held-out Portuguese grammatical margin, with no corresponding joint pattern in shuffled-Portuguese or matched-English controls.

Avoid:

> SLT proves that the model grokked Portuguese.

## Null-result submission

A scientifically useful null report can show that Portuguese behavior improved smoothly, that LLC was insensitive or sampler-dependent, and that transient checkpoints violated local-posterior assumptions. The report should then emphasize the methodological lesson and provide the diagnostic benchmark rather than framing the result as failure.
