# Hackathon submission guide

The public Apart event page asks for a PDF research report documenting approach, results, and implications. The event welcomes technical-safety work on Portuguese- and Spanish-language models. The mock report uses six pages, within the previously identified 4–8 page target from an official hub page.

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

## Minimum result package

- report PDF;
- code repository/commit;
- machine-readable run registry;
- all real figures and source CSVs;
- sampler traces;
- exact evaluation items or generation procedure;
- environment and checkpoint hashes;
- a `REPRODUCE.md` with one command per phase.

## Reporting language

Preferred:

> We found an LLC changepoint in the same checkpoint interval as a rise in held-out Portuguese grammatical margin, with no corresponding joint pattern in shuffled-Portuguese or matched-English controls.

Avoid:

> SLT proves that the model grokked Portuguese.

## Null-result submission

A scientifically useful null report can show that Portuguese behavior improved smoothly, that LLC was insensitive or sampler-dependent, and that transient checkpoints violated local-posterior assumptions. The report should then emphasize the methodological lesson and provide the diagnostic benchmark rather than framing the result as failure.
