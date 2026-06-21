# SLT Portuguese — Project Status

_Updated 2026-06-21 ~01:00 UTC. The current, authoritative summary of the project for collaborators and
their coding agents. For the blow-by-blow, see `state/decision_log.md`._

## The research question (this is the whole point)
Does an **SLT-derived geometric quantity — the Local Learning Coefficient (LLC)** — change in a way that
**aligns with a behavioral/developmental transition** as a small English-trained language model acquires
Portuguese via full-parameter continued pretraining?

**A model learning Portuguese is not itself a result** — it's the scaffolding that makes the geometric
question well-posed. The contribution is the LLC↔behavior alignment. If there is no valid LLC trajectory,
there is no result.

## Headline result (as of now — strong, single-seed; controls + robustness done)
After a hard debugging arc, we have a **complete, valid, positive LLC trajectory for the primary
condition (seed A, all 11 checkpoints to 100M)** that shows a **steep rise in geometric complexity during
acquisition, then a plateau** — with the steepest rise bracketing the behavioral grammar-acquisition
transition. **Both controls now confirm specificity:** token-shuffled PT rises to ~60 then *declines* to
~28, and matched-English rises only smoothly to ~70 — neither reproduces the rise-then-plateau. The shape
is also robust to localization (loc=100 vs loc=300 identical in shape). The remaining piece before a claim
is **seed-B replication**.

**→ Write-ups with figures: [`reports/seed_a_llc_trajectory/REPORT.md`](reports/seed_a_llc_trajectory/REPORT.md)
(primary) and [`reports/control_comparison/REPORT.md`](reports/control_comparison/REPORT.md) (controls + robustness).**

```
LLC (structured PT seed A, fixed non-padded reference, loc=100, 3 chains) — COMPLETE:
 400k +52.3 | 800k +61.5 | 1.5M +75.5 | 2.5M +80.7 | 4M +84.3 | 6M +84.8 | 8M +86.0 | 18M +85.3 | 27M +85.3 | 60M +85.8 | 100M +86.7
                                  ^^^^^^^^^^^^ behavioral transition ~1.5–2.5M ^^^^^^^^^^^^
```
All 11 checkpoints positive, tight chain agreement, zero rejected chains. (The LLC job exited non-zero on
a cosmetic `KeyError: 'estimated_cost_usd'` in the final-manifest writeout, *after* all sampling
finished — no scientific output affected.)

## Scientific state in detail
- **Training (frozen recipe):** TinyStories-8M, full-parameter FP32 AdamW, **lr 1e-4, 3% warmup, cosine
  decay, grad-clip 1.0, weight_decay 0.01, batch 64, Wikipedia-PT corpus**, sequence length 128. This recipe
  was found by a short autoresearch loop after an initial run (8M tokens, lr 3e-4 flat) failed to learn.
  - structured PT seed A: trained to **100M tokens**, PT BPB **6.7 → 2.5** (clean, monotonic).
  - shuffled PT control: **100M** done. matched-English control: ~**80M** (paused). structured PT seed B: **not started**.
- **Behavioral benchmarks (every checkpoint):** PT validation BPB, English-retention BPB, and a
  **538-item templated Portuguese grammatical minimal-pair benchmark** (`data/eval/pt_minimal_pairs.jsonl`,
  10 agreement phenomena, frozen+hashed; generator `scripts/gen_pt_minimal_pairs.py`, scorer
  `scripts/score_minimal_pairs.py`). Grammar accuracy rises **chance → ~89%** with a clean transition at
  **~1.5–2.5M tokens** (margin flips negative→positive there). The original 10-item probe was too noisy; this
  replaced it.
- **LLC (the hard part):** see below.

## The LLC debugging arc (important context — read before touching LLC)
1. The first LLC runs were **negative at every checkpoint, even the deepest 100M minimum.** We initially
   (wrongly) treated the campaign's accept/reject *label* as validity — but "accepted" only means "not
   severely downhill," NOT "positive." Always read the **actual value, sign, and chain agreement.**
2. Sweeping lr and localization could not fix it (lr→0 ⇒ LLC→0 from below; batch-size invariant) — the
   fingerprint of "the checkpoint is not a minimum of the loss being measured."
3. **Root cause (a real code/data bug):** `scripts/llc_campaign.py` builds its sampler reference from short
   OPUS sentences (~30 chars) **padded to 128 tokens with eos and never masked** — so ~90% of every scored
   sequence was unmasked eos-prediction. The checkpoint minimizes the *training* loss, not that padded loss.
4. **Fix:** rebuilt the reference from full-length **non-padded** Wikipedia-PT training chunks
   (`scripts/build_packed_reference.py`; the buggy original is saved as
   `…/data_splits/sampler_reference.jsonl.orig`). With it, LLC is **positive and accepted everywhere**
   (100M: +77.9 at loc=100). The original `loc=100` config was fine all along — the reference was the bug.
   - **TODO (open):** also mask padding *in the loss* inside `llc_campaign.py` (proper labels / ignore_index)
     so the fix is robust to any reference, not only via the repacked reference.

## What's done / running / pending
- ✅ Orchestrator + dashboard + recipe + behavioral benchmarks + behavioral transition found.
- ✅ LLC bug found & fixed; **complete** valid positive LLC trajectory for seed A (all 11 checkpoints to
  100M) — written up in [`reports/seed_a_llc_trajectory/REPORT.md`](reports/seed_a_llc_trajectory/REPORT.md).
- ✅ **Control LLC trajectories** — shuffled-PT (rises to ~60 then **declines to ~28**) and matched-English
  (smooth gentle rise to ~70, no changepoint). Neither reproduces the structured rise-then-plateau →
  the changepoint is **specific to PT acquisition**. All three AGENTS.md-minimum conditions now done.
- ✅ **Localization-sensitivity check** — structured-PT shape is identical at loc=100 vs loc=300 (~4 units
  apart, same rise+plateau). Controls + robustness written up in
  [`reports/control_comparison/REPORT.md`](reports/control_comparison/REPORT.md).
- ⏳ **seed B replication** — train to 100M + LLC; show the changepoint replicates. **Top remaining piece**
  (needs a clean training run — re-running training in place would clobber existing checkpoints).
- ⏳ **Statistical changepoint analysis** + literature framing (novelty vs known LLC-during-learning work).
- ⏳ **Code hygiene** — fix the cosmetic `KeyError: 'estimated_cost_usd'` (llc_campaign.py:652) and add
  in-loss padding masking.

## Infrastructure reality (important for a new collaborator)
- Experiments run on a **GCP L4 GPU VM** (`slt-portuguese-l4-mig`, zone `us-central1-b`, project
  `elvis-launchpad`). Cloud lifecycle, the OpenAI/Codex key (1Password), and `.env.local` are **operator-side
  and not in the repo.**
- **Cloning the repo gives you all the code + docs, but NOT the ability to run experiments**: the trained
  checkpoints (hundreds of MB), the large tokenized corpora, and the GPU VM are not in git. To actually run
  LLC/training you need GPU access (our VM, or your own GCP + re-training) — coordinate with the operator.
- Heavy artifacts are gitignored (checkpoints, `*.zarr`, `*token_ids*.jsonl`). The repo holds code, prompts,
  docs, the benchmark, and small result summaries.

## Where things live
- Autonomous research harness: `codex/orchestrate.py` (+ `codex/prompts/`, `codex/schemas/`); rules in `AGENTS.md`.
- Local control dashboard: `apps/dashboard/` (`pnpm dashboard:dev`).
- LLC: `scripts/llc_campaign.py` (run), `scripts/llc_curve.py` (read values from `running_estimates/`),
  `scripts/build_packed_reference.py` (the reference fix).
- Grammar benchmark: `data/eval/pt_minimal_pairs.jsonl`, `scripts/gen_pt_minimal_pairs.py`, `scripts/score_minimal_pairs.py`.
- Results on the VM under `results/02_final_training/...` (training) and `results/03_llc_campaign/...` (LLC).
- Running narrative & decisions: `state/decision_log.md`.

## For a new collaborator / coding agent — suggested read order
1. This file, then `state/decision_log.md` (the full arc, esp. the LLC fix).
2. `AGENTS.md` (the scientific rules — incl. the validity gate and "don't manufacture a changepoint").
3. `scripts/llc_campaign.py` + `scripts/build_packed_reference.py` (the LLC machinery and the fix).
4. `data/eval/pt_minimal_pairs.jsonl` (the behavioral benchmark).

**Good delegatable tasks** (✱ = needs GPU/VM access; others are code/analysis/writing):
- Harden the LLC code: mask padding in `llc_campaign.py` and re-validate. (code; ✱ to verify)
- ✱ Localization-sensitivity analysis of the LLC trajectory (rigor check).
- ✱ Control LLC trajectories (shuffled-PT, English) for contrast; ✱ seed-B replication.
- Statistical changepoint analysis: quantify the LLC changepoint and its alignment with the ~1.5–2.5M behavioral transition.
- Expand the grammar benchmark toward a larger BLiMP-PT-scale set (extend the templated generator). (code)
- Draft the report/figures from the result tables; literature framing vs developmental-interpretability/SLT work.
