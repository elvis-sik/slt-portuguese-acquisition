# Recipe search (rapid autoresearch)

Goal: in many SHORT attempts, find a training recipe that makes the small English-trained model
(TinyStories-8M) **actually start learning Portuguese** — structured-Portuguese validation BPB must
decrease — before committing to any long or expensive run. This is a fast search over the TRAINING
RECIPE, not a final scientific result. Run it like a tight experiment loop: hypothesize → short run →
measure → keep the best → iterate. Stay on the small model; do not switch to a larger model here.

Read `AGENTS.md` (especially the scientific validity gate). Then, each attempt:

1. **Choose a recipe to test.** Vary the knobs that fix instability / non-learning: base learning
   rate, warmup fraction, LR schedule (cosine/linear decay), gradient clipping, weight decay, batch
   size, and tokens-per-attempt. Start from a sane default (e.g. lr 1e-4–3e-5, ~3% warmup, cosine
   decay, grad-clip 1.0) and adjust based on the previous attempt's curve. Change one or few knobs at
   a time so you can attribute the effect.
2. **Ensure a sufficient Portuguese corpus.** If OPUS-100 en-pt is too small to supply fresh tokens
   for an attempt (re-reading the same tiny set is not a real learning test), pull a streaming slice
   of a larger PT corpus (OSCAR / CC-100-pt / mC4-pt). Keep one fixed Portuguese validation/eval set
   across all attempts so scores are comparable.
3. **Run a SHORT bounded training** (target ~5–15 minutes / a few tens of millions of tokens) on
   structured Portuguese, **checkpointing at the end**. When you want to confirm real structure (not
   noise memorization), run a matched shuffled-Portuguese control attempt with the same recipe.
4. **Measure the learning signal.** Does structured-PT validation BPB DECREASE over the attempt, is it
   stable (no divergence/NaNs), and does it beat the shuffled control? Record the recipe, BPB
   slope/endpoints, stability, wall time, and the checkpoint path. Keep the best recipe so far.
5. **Preserve every attempt** (recipe + curve + checkpoint); never overwrite. Update state/registry so
   the search is fully auditable.

Stop conditions:

- **Recipe found** — a recipe clearly works (structured-PT BPB decreasing, stable, beating the
  shuffled control). Return `status: completed`, `gate_decision: proceed`, and in the summary name the
  winning recipe and its checkpoint path, and recommend: *continue this recipe from its checkpoint to
  a larger token budget*. Do NOT start the long run yourself — the planner halts for an operator
  greenlight first.
- **No recipe works** within the budget/time window — return `status: blocked` /
  `gate_decision: pivot` (or escalate) with what was tried and the leading hypotheses (model too
  small, corpus too small, needs more tokens/different schedule). Never report a non-learning result
  as a scientific finding.

Efficiency: keep each attempt short; prefer more short attempts over fewer long ones. The deliverable
of this phase is a **verified recipe + a checkpoint to continue from**, not a finished experiment.
