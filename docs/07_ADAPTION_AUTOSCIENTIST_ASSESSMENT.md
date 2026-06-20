# Adaption AutoScientist assessment

## Publicly stated capability

Adaption's public AutoScientist page says the user specifies an outcome and the system co-optimizes data and training recipes until performance converges, then deploys the adapted model.

That is potentially useful for ordinary training-recipe or data optimization. The public page does not establish the controls required for this SLT experiment: raw frequent checkpoint export, full-parameter training, exact tokenizer retention, deterministic data order/seeds, arbitrary custom evaluation callbacks, optimizer-state export, or custom `devinterp` execution.

## Recommendation

Do not put AutoScientist on the critical path. Qualify it quickly, then use it only if it passes the relevant interface checks.

## Thirty-minute qualification checklist

Ask the service/support/UI to demonstrate all of the following:

| Requirement | Pass condition |
|---|---|
| Model import | can load the exact TinyStories/Hugging Face causal LM revision |
| Full-parameter continuation | not adapter-only or opaque weight merging |
| Objective control | exact next-token loss and optimizer settings are visible |
| Tokenizer control | original tokenizer retained and exportable |
| Data control | exact examples, ordering, seeds, and split hashes are recordable |
| Frequent checkpoints | export at specified cumulative-token milestones |
| Raw export | standard unquantized HF/PyTorch weights, preferably safetensors |
| Optimizer state | exportable for continuation/recovery |
| Logs | step-level loss, LR, tokens, runtime, and failures downloadable |
| Custom evaluation | can run or export for local grammar/BPB evaluation |
| Custom code | can execute arbitrary Python or at least allow checkpoints to move to GCP |
| Queue and pricing | known before launch; turnaround fits the remaining sprint |

Hard failures for the primary experiment:

- no raw checkpoint export;
- only final model export;
- adapter-only/black-box training;
- tokenizer or data recipe cannot be fixed;
- no way to run `devinterp` on exported weights;
- optimization target uses the held-out grammar test.

## Scientific concern: adaptive optimization can contaminate the study

AutoScientist advertises co-optimization of data and recipe against a desired outcome. If that desired outcome is the same grammar metric used to claim a developmental transition, the system can overfit the evaluation or select a trajectory because it looks transition-like. This creates strong researcher/optimizer degrees of freedom.

If used:

1. keep a private confirmatory grammar set that AutoScientist never sees;
2. predeclare the recipe/data search space;
3. use AutoScientist only on a development metric;
4. freeze the selected recipe;
5. rerun the confirmatory trajectory from scratch on GCP with full logging and checkpoints;
6. label the AutoScientist phase exploratory.

## Good uses in this project

- generating candidate data-cleaning rules;
- choosing among a small predeclared learning-rate/batch grid;
- producing an auxiliary optimized Portuguese checkpoint;
- testing whether its chosen recipe transfers to a frozen confirmatory run.

## Poor uses

- the sole source of training checkpoints;
- performing opaque automatic training whose trajectory cannot be reconstructed;
- selecting sampler settings;
- optimizing directly for a sharp transition;
- replacing custom SGLD/LLC execution.

## Decision rule

Use Adaption only when it saves more time than its integration consumes and preserves raw reproducibility. Otherwise, the GCP worker remains both the training and SLT platform.
