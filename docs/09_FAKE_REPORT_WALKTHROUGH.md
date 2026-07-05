# Walkthrough of the synthetic report

> Status, 2026-06-21: historical explanation of the fabricated mock report. It documents a planning
> visualization only; current empirical results are in `PROJECT_STATUS.md` and `reports/`.

The report at `reference/mock_report/slt_portuguese_synthetic_mock_submission.pdf` is a visualization of a moderately successful outcome. It is not a forecast and not evidence.

## Page 1: the project in one minute

The fake abstract says lexical knowledge improves smoothly, grammar improves rapidly around 3.4 million Portuguese tokens, and normalized LLC peaks then drops in the same interval. It immediately states that the result would support only a limited marker claim, not a universal phase transition.

This page demonstrates the required compression: one question, one result, one caveat, and why Portuguese-language model adaptation is relevant.

## Page 2: why the result would be interpretable

The methods table makes the controls legible:

- structured Portuguese;
- matched English continuation;
- shuffled Portuguese;
- three seeds;
- continuous grammar margins;
- LLC with multiple localized SGLD chains.

The synthetic sampler diagnostic is crucial. Without a trace showing chains settle into a common range, the LLC scalar would look like an unverified function output.

## Page 3: behavior before geometry

Figure 1a shows Portuguese validation BPB falling in two regimes. The shuffled control initially tracks structured Portuguese, suggesting early gains are compatible with token-frequency/local-sequence learning.

Figure 1b shows the primary grammar margin. Structured Portuguese rises after early lexical learning; controls stay near zero. A continuous margin prevents an apparent jump caused solely by accuracy crossing 50%.

In a real report, this page is valuable even if LLC later fails. It establishes whether there is a behavioral phenomenon worth explaining.

## Page 4: the geometric claim and controls

Figure 1c shows normalized LLC rising and then dropping near the grammar change. The table reports structured Portuguese, shuffled Portuguese, and matched English side by side. The most useful fabricated detail is that shuffled Portuguese reaches high lexical accuracy but near-chance grammar and no LLC changepoint. That weakens a vocabulary-only explanation.

The page also reports English forgetting. A credible adaptation report should not pretend Portuguese capability is free.

## Page 5: uncertainty and replication

The fake seed-level scatter places LLC and grammar changepoints near the diagonal. This is more convincing than one smooth average curve. The Spanish extension is deliberately described as exploratory because tokenization and pretraining overlap confound cross-language timing.

The real weekend plan should omit Spanish until the Portuguese controls and second seed are complete.

## Page 6: limited causality and honest boundaries

The fake report localizes a susceptibility increase to a final MLP and freezes that component before the transition. The freeze delays grammar more than a matched control freeze. This is moderately good causal evidence, but capacity reduction remains a confound.

The final interpretation explicitly rejects three stronger claims:

- all language acquisition is phase-like;
- LLC causes the capability;
- the phenomenon necessarily scales to frontier models.

## What is intentionally optimistic

- three clean seeds;
- a clear structured/shuffled separation;
- stable SGLD at transient checkpoints;
- a well-aligned changepoint;
- a useful localized component;
- enough time for a freeze intervention and Spanish replication.

A real good-enough submission can be narrower: one main seed, reduced second-seed confirmation, two controls, a valid sampler diagnostic, and a cautious aligned-changepoint result.

## How real outputs replace fake outputs

| Synthetic artifact | Real source |
|---|---|
| `synthetic_training_trajectories.csv` | merged checkpoint behavior metrics |
| `synthetic_changepoints.csv` | frozen changepoint analysis script |
| `synthetic_condition_summary.csv` | real final checkpoint aggregation |
| `figure_1b_grammar_margin.png` | evaluation pipeline output |
| `figure_1c_llc_trajectory.png` | chain-level LLC aggregation |
| `figure_s1_sampler_diagnostic.png` | raw sampler loss traces |
| fake intervention table | optional branch-training result |

Never edit synthetic CSV values into real tables. Generate a parallel `results/report/` tree from empirical run IDs.

## Reading the synthetic numbers

The effect sizes were selected to be visible and scientifically plausible-looking, not predicted. “3.4 million tokens,” “11.1% LLC drop,” and “418-step delay” are narrative devices. The real project should predeclare analysis and accept whatever scale or null result occurs.
