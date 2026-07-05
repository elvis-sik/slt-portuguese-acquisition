# SLT Portuguese: does a model's local geometry change as it acquires a language?

A developmental-interpretability experiment. We take a small English-trained language model
(TinyStories-8M), adapt it to Portuguese by full-parameter continued pretraining, and ask whether an
**SLT-derived geometric quantity — the Local Learning Coefficient (LLC)** — changes in a way that
**aligns with a behavioral transition** (the onset of Portuguese grammatical competence).

> The model learning Portuguese is *not* the result — it's the scaffolding. The contribution is the
> **LLC ↔ behavior alignment.**

## Current status — archived result

_Archived 2026-07-05. The hackathon is over and the GCP/remote VMs used for the sprint are no longer
running. This repository is the code, compact-results, and provenance companion to the submission._

**→ See [`PROJECT_STATUS.md`](PROJECT_STATUS.md) for the authoritative result summary and
[`FUTURE_WORK.md`](FUTURE_WORK.md) for follow-up ideas.** Headline:

- The model genuinely acquires Portuguese (PT bits-per-byte 6.7 → 2.5), with a clean **behavioral
  grammar-acquisition transition at ~1.5–2.5M tokens** measured on a 538-item Portuguese minimal-pair
  benchmark (chance → ~89%).
- After fixing a real LLC-measurement bug (an unmasked-padding loss-definition error — see PROJECT_STATUS
  and `state/decision_log.md`), we obtain a **valid, positive LLC trajectory** that **rises steeply through
  the acquisition phase and then plateaus** — an aligned-changepoint signature.
- **Both controls now confirm specificity:** token-shuffled PT rises then *declines* to ~28, and matched
  English rises only smoothly to ~70 — neither reproduces the rise-then-plateau (~85). The shape is also
  **robust to localization** (loc=100 vs 300 identical). So the changepoint is specific to genuine
  Portuguese acquisition, not training length or generic adaptation —
  [`reports/control_comparison/REPORT.md`](reports/control_comparison/REPORT.md).
- A second Portuguese seed is useful follow-up work, but the current submission claim is deliberately
  narrower: one primary Portuguese seed, two controls, and a localization check.

The hackathon submission write-up lives outside Git as a shared Google Doc. The old generated TeX/PDF
draft and the earlier 8M diagnostic report package were removed from the GitHub-facing tree so reviewers
do not trip over stale artifacts.

This repo was originally a *planning handoff*; it is now a project that has been built and run. Several
files under `docs/`, plus `START_HERE_FOR_CODEX.md` and `reference/mock_report/`, are **historical
planning artifacts** — see the note at the bottom. `PROJECT_STATUS.md` and `state/decision_log.md` are the
authoritative, current sources.

## How it worked

The experiment was driven by an **autonomous research harness** on a GCP GPU VM, watched from a local
dashboard. The VMs are now gone, but the operational structure was:

```
local workstation                          GCP L4 GPU VM
-----------------                          -------------
dashboard (apps/dashboard, pnpm)  <—sync—  orchestrator: planner + executor agents (codex/orchestrate.py)
gcloud lifecycle (infra/gcp)      ——————>  bounded training / LLC (SGLD) jobs
                                           checkpoints, traces, decision log, results/
```

- **`codex/orchestrate.py`** — a deterministic harness that loops a **planner** agent (chooses the next
  step + budget) and an **executor** agent (did the work), with hard backstops (cost cap, wall-clock
  deadline, stop-file) and a two-layer self-stop. Scientific rules live in **`AGENTS.md`**.
- **`apps/dashboard/`** — a local Next.js dashboard (`pnpm dashboard:dev`) showing the orchestrator
  timeline, experiment runs, and readable agent transcripts; it syncs results from the VM.
- **Experiment scripts** — training, the LLC/SGLD campaign, and a templated Portuguese grammar benchmark
  (see "Where things live").

## Getting oriented (read order)

1. [`PROJECT_STATUS.md`](PROJECT_STATUS.md) — current state, results, and the LLC debugging arc.
2. [`state/decision_log.md`](state/decision_log.md) — the full running narrative of decisions.
3. [`AGENTS.md`](AGENTS.md) — the scientific rules (validity gate; never manufacture a changepoint).
4. [`REPRODUCE.md`](REPRODUCE.md) — what can be checked from Git alone versus what needs the GPU/checkpoint environment.
5. [`FUTURE_WORK.md`](FUTURE_WORK.md) — the remaining SLT work and the low-resource guardrail extension.
6. `scripts/llc_campaign.py` + `scripts/build_packed_reference.py` — the LLC machinery and the reference fix.
7. `data/eval/pt_minimal_pairs.jsonl` — the behavioral benchmark (generator/scorer in `scripts/`).

## Running it

Cloning gives you **all the code, docs, and the full narrative — enough to read the project and generate
ideas.** It does **not** let you run experiments: the trained checkpoints (hundreds of MB), tokenized
corpora, the GPU VM, and the OpenAI/Codex key (1Password) and `.env.local` are operator-side and not in
git. The original VMs have been removed. To actually rerun training/LLC, start from fresh GPU capacity or
from an external boot-disk snapshot if one still exists.

The dashboard runs locally with `pnpm dashboard:dev`, but only does live work when pointed at a running VM.

## Where things live

| What | Where |
| --- | --- |
| Autonomous harness + agent prompts/schemas | `codex/orchestrate.py`, `codex/prompts/`, `codex/schemas/` |
| Scientific rules | `AGENTS.md` |
| Reproduction notes | `REPRODUCE.md` |
| Future work | `FUTURE_WORK.md` |
| Local control dashboard | `apps/dashboard/` |
| LLC campaign / read values / reference fix | `scripts/llc_campaign.py`, `scripts/llc_curve.py`, `scripts/build_packed_reference.py` |
| Portuguese grammar benchmark | `data/eval/pt_minimal_pairs.jsonl`, `scripts/gen_pt_minimal_pairs.py`, `scripts/score_minimal_pairs.py` |
| VM lifecycle / launcher / watchdog | `infra/gcp/`, `infra/remote/` |
| Judge-facing result summaries | `reports/seed_a_llc_trajectory/`, `reports/control_comparison/`, `reports/submission/README.md` |
| Results (training, LLC) | `results/02_final_training/`, `results/03_llc_campaign/` (heavy artifacts and operational traces gitignored) |
| Running narrative & decisions | `state/decision_log.md` |

## ⚠️ Synthetic reference report

Everything under **`reference/mock_report/` is fabricated** — a synthetic planning artifact that helped
visualize what the project could look like if the idea proved good. Every number, figure, effect size, and
changepoint in it is fake. Now that real results exist, **never mix the mock report with empirical
results.** Real outputs live under `results/`, and the current narrative summaries live under `reports/`.

## Historical planning artifacts

`START_HERE_FOR_CODEX.md`, much of `docs/` (the executive plan, three-day plan, Fermi estimates, etc.), and
`reference/mock_report/` date from the original pre-implementation handoff and may not reflect what was
actually built or found. Treat `PROJECT_STATUS.md` + `state/decision_log.md` as the source of truth.
