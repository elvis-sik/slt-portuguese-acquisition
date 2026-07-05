# Failure modes and pivots

> Status, 2026-06-21: historical planning document. It remains useful context for why the report is
> cautious, but current findings are summarized in `PROJECT_STATUS.md` and `reports/`.

## GCP quota or no G2 capacity

Try two additional documented G2 zones. If not solved quickly, use another 24 GB GPU provider. Keep the same repository and benchmark protocol. Do not spend the research window debugging billing/quota.

## GPU driver or PyTorch CUDA failure

Run the official Google driver installer again after reboot. Verify driver before reinstalling Python packages. If PyTorch is CPU-only, reinstall a CUDA-enabled wheel appropriate to the current PyTorch selector. Preserve the environment log.

## `devinterp` architecture incompatibility

Confirm the minimal expected Hugging Face causal-LM interface. If the issue is model-specific, move from GPT-Neo TinyStories to a similarly small GPT-NeoX/Pythia-style checkpoint or a minimal in-repo causal transformer. Record that the base model changed before collecting final results.

## Sampler drifts downhill at intermediate checkpoints

Increase localization, test the predeclared `n_beta` alternatives, and inspect center loss. If no common configuration works across early/middle/late checkpoints, do not report comparable LLC. Pivot to:

1. a controlled micro-language where checkpoints can be trained closer to plateaus;
2. a methodological report on the failure of localized sampling along a nonstationary adaptation path;
3. simpler curvature/gradient diagnostics clearly labeled non-SLT substitutes.

## No behavioral transition

Do not force a changepoint. Increase checkpoint density only under the predeclared adaptive rule. If behavior remains smooth, report the null or pivot to a controlled Portuguese-like grammar with held-out compositions.

## Grammar probe fails sanity checks

Verify sentence scoring, token masking, length normalization, and common-prefix handling. Test a Portuguese-capable reference model and a deliberately untrained baseline. Reduce the probe to high-confidence agreement templates. Do not proceed on an evaluation that cannot distinguish known-good from chance.

## Structured and shuffled Portuguese look the same

The shuffle may preserve too much local structure or the model may only be learning lexical statistics. Try stronger sequence-level permutation while matching unigram distribution. If grammar stays near chance in both, use a micro-language where structure is learnable under the budget.

## Training is unexpectedly slow

Profile data loading and evaluation callbacks; cache tokenized data; reduce checkpoint serialization frequency while preserving milestone checkpoints; test sequence length 64; ensure GPU is used. Do not scale up until one trajectory is comfortably below one hour.

## Disk pressure

Keep optimizer state only at recovery checkpoints; save weights at analysis checkpoints; compress logs; upload/download artifacts; never silently delete the only copy of a run.

## Adaption integration consumes time

Stop after the qualification window. Treat it as optional. The primary path is GCP.

## Report deadline pressure

Cut stretch experiments first. A coherent result with one main seed, controls, sampler diagnostics, and honest uncertainty is better than an unfinished intervention or multilingual comparison.
