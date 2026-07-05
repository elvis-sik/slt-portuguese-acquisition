# Future Work

_Updated 2026-07-05. The hackathon run is archived: the GCP/remote VMs used for the sprint are no
longer running, and no continuation job should be assumed to exist._

The current submission claim is intentionally narrow: one structured-Portuguese seed with matched
controls and a localization check. The repo also contains exploratory low-resource guardrail artifacts
that suggest a natural next project. This page separates those ideas from the completed evidence.

## Highest-priority follow-ups

1. **Clean seed-B replication.** Train an independently seeded structured-Portuguese run and compute the
   same 11-checkpoint LLC trajectory. The attempted in-place seed-B continuation was not a usable
   replication: one run was byte-identical to seed A because data order was deterministic, and the later
   rerun did not produce an archived result before the VMs were removed.
2. **Formal changepoint and alignment analysis.** Fit changepoint models to the LLC trajectory and the
   538-item grammar margins, then quantify whether the LLC change is aligned with, leading, or merely
   adjacent to the behavioral transition around 1.5M-2.5M tokens.
3. **Harden the LLC implementation.** Mask padding in the sampler loss itself, fix the cosmetic
   `estimated_cost_usd` manifest `KeyError`, add a CPU/tiny-model regression test for the padding bug,
   and make the accept/reject diagnostics report sign, chain agreement, and downhill movement in one
   obvious summary.
4. **Broaden robustness checks.** Add loc=30 and possibly loc=1000 for the primary trajectory, score the
   grammar benchmark at later checkpoints, and expand the templated Portuguese benchmark toward a
   BLiMP-PT-scale suite with stronger linguistic coverage.
5. **Package the scientific story.** Tighten the literature framing against prior LLC-during-training,
   developmental-interpretability, and cross-lingual adaptation work; keep the claim at "an
   SLT-derived geometric changepoint aligned with a behavioral transition," not a formal phase
   transition.

## Low-resource guardrail extension

The untracked-to-now guardrail materials are exploratory evidence for a second research direction:
whether safety classifiers and their local geometry degrade or reorganize when moved into languages that
are underrepresented in guardrail training.

1. **MrGuard low-resource audit.** `scripts/mrguard_multijail.py` evaluates MrGuard on MultiJail harmful
   prompts. The compact result in `results/mrguard/multijail_summary.json` shows lower unsafe-recall on
   Swahili and Bengali than on English/Arabic in the sampled run. This is a benchmark prompt for a larger,
   cleaner audit, not a final claim.
2. **EN/ES/PT guardrail slice.** `scripts/build_guardrail_bench.py` creates a small English, Spanish, and
   Portuguese benchmark with a Brazilian-stressor slice. Spanish is in-domain for MrGuard; Portuguese is
   an unseen sister-language contrast. The next step is to run and report this benchmark with multiple
   guardrail baselines.
3. **Swahili guardrail acquisition trajectory.** `scripts/h100/swahili_guardrail_sft.py` trains a LoRA
   moderation classifier over Swahili prompts and saves dense checkpoints. The archived pod summaries show
   Swahili held-out accuracy rising from about 0.31 at step 0 to about 0.95 by step 600, with unsafe-recall
   reaching 1.0 in the sampled evaluation.
4. **Guardrail LLC trajectory.** `scripts/h100/llc_sgld.py` is a self-contained SGLD estimator for the
   Swahili moderation loss. The calibration work found template-mismatch and sampler-validity problems;
   the saved H100 LLC value at step 400 is negative/invalid, while a later fixed-template calibration
   produced only a tiny positive value. A future run should redo the full trajectory with a predeclared,
   validated sampler config before making any geometric claim.

## Reproducibility work

1. **Fresh infrastructure recipe.** Because the original VMs are gone, document a from-scratch GPU setup
   or recreate from a preserved boot-disk snapshot if one exists outside Git.
2. **Artifact manifest.** Record which heavy artifacts still exist outside the repository: checkpoints,
   tokenized corpora, zarr traces, pod outputs, and Google Doc exports.
3. **GitHub-facing release.** Keep only compact summaries in Git; publish large artifacts separately if
   they are needed for review or replication.
