# SLT Portuguese — Project Status

_Generated 2026-06-20 ~17:46 UTC. Snapshot of the project state for tracking/submission prep._

## Goal
Test whether an SLT-derived measure (local learning coefficient, LLC) changes when a small
English-trained LM acquires Portuguese via full-parameter continued pretraining, with token-shuffled
Portuguese and matched-English controls.

## Engineering (built this session, working)
- **Autonomous orchestrator** (`codex/orchestrate.py`): planner agent (GPT-5.5/xhigh) + executor agent
  (GPT-5.5/high, `danger-full-access` for GPU) + deterministic harness enforcing hard backstops
  ($50→adjustable hard cap, wall-clock deadline, operator stop-file). Per-tick state in
  `results/_orchestrator/state.json`.
- **Scientific validity gate** (AGENTS.md + phase/planner prompts): a degrading model or negative LLC
  is treated as a pipeline bug to fix/escalate, never reported as a "null". Planner cannot declare
  `complete` on a broken run.
- **recipe_search autoresearch** (`codex/prompts/recipe_search.md`): many SHORT training attempts to
  find a recipe that demonstrably learns Portuguese, then halt for operator greenlight before scaling.
- **Two-layer self-stop**: dashboard auto-stop on completion + VM-side `completion_watchdog.sh`
  (30-min grace, `sudo shutdown`) so a fast finish can't idle-bill. GPU preflight in the launcher.
- **Dashboard** (`apps/dashboard`): Orchestrator tab (tick timeline, deadline/cost bars), Experiment
  runs, Agent-log tab (readable Codex transcripts), figures/metrics. Syncs from the VM (png/pdf/svg
  included).

## Infrastructure
- Active VM: **`slt-portuguese-l4-mig`** (g2-standard-4 / L4) in **`us-central1-b`**, RUNNING.
- Migrated from `us-central1-a` after an L4 **stockout**; boot disk snapshot
  **`slt-pt-migrate-snap`** retained as backup; old VM + disk deleted.
- Codex auth (`~/.codex/auth.json`) persisted via the snapshot. Key sourced from 1Password.

## Scientific status
- **Night 1 (8M tokens): honest NULL / broken pipeline.** The 8M model did NOT learn Portuguese
  (PT BPB rose) and LLC came out negative (non-physical). Root causes: token budget far too small +
  unstable LR (3e-4 flat). The agent initially mis-reported this as a "null" — fixed by the validity
  gate. Report: `results/04_report/report_20260620T064400Z_final_training_20260620T053855Z_batch16/`
  (figures show flat/degrading behavior and negative LLC; **stale** w.r.t. current direction).
- **Recipe verified (recipe_search, 1M tokens).** Frozen recipe: TinyStories-8M, FP32 AdamW, **lr 1e-4,
  3% warmup, cosine decay, grad-clip 1.0, weight_decay 0.01, batch 64, Wikipedia-PT corpus**.
  Structured-PT BPB **6.77 → 4.81 → 4.33 → 4.08 → 3.81** (monotonic), beating the shuffled control
  (4.21). English retention degraded as expected. Caveat: tiny 24-example validation set.
- **Scale-up IN PROGRESS (~100M tokens/condition).** Running now under the frozen recipe with a larger
  validation set + dense checkpoints; deadline ~01:40 UTC 2026-06-21. Open question: does the clean
  BPB descent **hold at 100M tokens**? Then LLC campaign + report. A 20-min follow-up check is
  scheduled.

## Key artifacts
- Running project log: `state/decision_log.md` (current through the scale-up greenlight).
- Live orchestrator state: `results/_orchestrator/state.json` (on the VM; syncs to dashboard).
- Stale science report: `results/04_report/.../report.md` (night-1 failed run).
- Implementation plan: `~/.claude/plans/okay-this-does-make-purring-waffle.md`.

## Git
- Remote: `github.com/elvis-sik/slt-portuguese-handoff`. **45 files uncommitted, nothing pushed** this
  session (the whole orchestrator system + synced results). Recommend committing + pushing before
  submission.

## Next steps
1. Read the scale-up verdict (follow-up check fires ~18:04 UTC): did the recipe hold at 100M tokens?
2. If yes → LLC campaign on the trajectory → fresh empirical report (replaces the stale one).
3. Commit + push the orchestrator system and results.
4. If the recipe degrades at scale → diagnose (the validity gate forces this) rather than report.
