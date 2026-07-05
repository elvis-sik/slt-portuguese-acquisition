# SLT Portuguese — Project Status

_Archived 2026-07-05 for the GitHub submission surface. This is the authoritative summary of the
completed hackathon run for collaborators, reviewers, and coding agents. The GCP/remote VMs used during
the sprint are no longer running. For the blow-by-blow, see `state/decision_log.md`; for follow-up ideas,
see `FUTURE_WORK.md`._

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
at the stronger replication level is a second structured-Portuguese seed. The current submission claim is
therefore scoped to one primary seed plus controls and localization robustness.

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
  - shuffled PT control: **100M** done. matched-English control: evaluated through the shared LLC
    checkpoints and used as the generic-adaptation control. structured PT seed B remains follow-up work.
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
   - **Open code hygiene:** also mask padding *in the loss* inside `llc_campaign.py` (proper labels /
     ignore_index) so the fix is robust to any reference, not only via the repacked reference.

## What's done / pending
- ✅ Orchestrator + dashboard + recipe + behavioral benchmarks + behavioral transition found.
- ✅ LLC bug found & fixed; **complete** valid positive LLC trajectory for seed A (all 11 checkpoints to
  100M) — written up in [`reports/seed_a_llc_trajectory/REPORT.md`](reports/seed_a_llc_trajectory/REPORT.md).
- ✅ **Control LLC trajectories** — shuffled-PT (rises to ~60 then **declines to ~28**) and matched-English
  (smooth gentle rise to ~70, no changepoint). Neither reproduces the structured rise-then-plateau →
  the changepoint is **specific to PT acquisition**. All three AGENTS.md-minimum conditions now done.
- ✅ **Localization-sensitivity check** — structured-PT shape is identical at loc=100 vs loc=300 (~4 units
  apart, same rise+plateau). Controls + robustness written up in
  [`reports/control_comparison/REPORT.md`](reports/control_comparison/REPORT.md).
- ⏳ **Seed-B replication** — valuable follow-up for a stronger robustness claim, but not part of the
  current Google Doc submission claim. The attempted rerun did not produce an archived, usable
  replication before the VMs were removed.
- ⏳ **Statistical changepoint analysis** + literature framing (novelty vs known LLC-during-learning work).
- ⏳ **Code hygiene** — fix the cosmetic `KeyError: 'estimated_cost_usd'` (llc_campaign.py:652) and add
  in-loss padding masking.
- ⏳ **Low-resource guardrail extension** — exploratory MrGuard, EN/ES/PT, and Swahili guardrail artifacts
  are preserved as follow-up material, not as part of the primary SLT-Portuguese claim. See
  [`FUTURE_WORK.md`](FUTURE_WORK.md).

## Infrastructure reality (important for a new collaborator)
- Experiments ran on a **GCP L4 GPU VM** (`slt-portuguese-l4-mig`, zone `us-central1-b`, project
  `elvis-launchpad`) and later on remote GPU/pod capacity for exploratory guardrail work. Those VMs are
  no longer running. Cloud lifecycle, the OpenAI/Codex key (1Password), and `.env.local` were
  **operator-side and not in the repo.**
- **Cloning the repo gives you all the code + docs, but NOT the ability to run experiments**: the trained
  checkpoints (hundreds of MB), the large tokenized corpora, the zarr traces, and the GPU machines are not
  in git. To actually run LLC/training you need fresh GPU access or an external boot-disk/artifact snapshot.
- Heavy artifacts are gitignored (checkpoints, `*.zarr`, `*token_ids*.jsonl`). The repo holds code, prompts,
  docs, the benchmark, and small result summaries. Operational Codex transcripts and bounded-job runner
  logs are also gitignored; they are useful for local debugging but not judge-facing evidence.

## Submission surface
- **Primary write-up:** shared Google Doc, not the stale TeX/PDF draft.
- **GitHub evidence:** this repository, especially `README.md`, this file, `reports/control_comparison/`,
  `reports/seed_a_llc_trajectory/`, `data/eval/pt_minimal_pairs.jsonl`, `scripts/`, `configs/`, and
  machine-readable summaries under `results/02_final_training/` and `results/03_llc_campaign/`.
- **Historical planning artifacts:** `docs/`, `START_HERE_FOR_CODEX.md`, and `reference/mock_report/` are
  retained for transparency. The mock report is fabricated and clearly labeled; it was a planning
  visualization, not evidence.

## Where things live
- Autonomous research harness: `codex/orchestrate.py` (+ `codex/prompts/`, `codex/schemas/`); rules in `AGENTS.md`.
- Local control dashboard: `apps/dashboard/` (`pnpm dashboard:dev`).
- LLC: `scripts/llc_campaign.py` (run), `scripts/llc_curve.py` (read values from `running_estimates/`),
  `scripts/build_packed_reference.py` (the reference fix).
- Grammar benchmark: `data/eval/pt_minimal_pairs.jsonl`, `scripts/gen_pt_minimal_pairs.py`, `scripts/score_minimal_pairs.py`.
- Results on the VM under `results/02_final_training/...` (training) and `results/03_llc_campaign/...` (LLC).
- Running narrative & decisions: `state/decision_log.md`.
- Future work and archived side ideas: `FUTURE_WORK.md`.

## For a new collaborator / coding agent — suggested read order
1. This file, then `state/decision_log.md` (the full arc, esp. the LLC fix).
2. `AGENTS.md` (the scientific rules — incl. the validity gate and "don't manufacture a changepoint").
3. `FUTURE_WORK.md` (what remains and what is merely exploratory).
4. `scripts/llc_campaign.py` + `scripts/build_packed_reference.py` (the LLC machinery and the fix).
5. `data/eval/pt_minimal_pairs.jsonl` (the behavioral benchmark).

**Good delegatable tasks** (✱ = needs GPU/VM access; others are code/analysis/writing):
- Harden the LLC code: mask padding in `llc_campaign.py` and re-validate. (code; ✱ to verify)
- ✱ Clean seed-B replication, from a fresh independent run, not an in-place continuation.
- Statistical changepoint analysis: quantify the LLC changepoint and its alignment with the ~1.5–2.5M behavioral transition.
- Expand the grammar benchmark toward a larger BLiMP-PT-scale set (extend the templated generator). (code)
- Draft the report/figures from the result tables; literature framing vs developmental-interpretability/SLT work.
- Turn the exploratory guardrail artifacts into a separate low-resource safety/LLC project. (mostly code/analysis; ✱ for full reruns)
