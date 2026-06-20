# Executive plan

## Decision

Proceed, but treat this as an SLT sampling project with a language-training component, not as ordinary fine-tuning plus one callback.

The model is trained conventionally with AdamW. At selected checkpoints, training stops conceptually: the checkpoint is frozen as a center point, and a separate localized Bayesian sampler probes the nearby loss geometry. This means the training loop itself does not need to become Bayesian, but the entire checkpoint, reference-data, sampler-tuning, diagnostics, and analysis protocol must be designed before the final run.

## Primary question

Can an SLT-derived local geometric estimate detect a developmental changepoint while a small English-trained model acquires Portuguese, and does that changepoint align with compositional grammatical generalization rather than only vocabulary exposure?

## Minimum credible experiment

- TinyStories-3M pilot; TinyStories-8M final.
- Full-parameter continued pretraining, not LoRA.
- Structured Portuguese: two seeds.
- Token-shuffled Portuguese: one seed.
- Matched English continuation: one seed.
- Behavioral evaluation at approximately eleven log-spaced checkpoints.
- Full LLC trajectory for the first Portuguese seed, reduced LLC replication for the second seed and controls.
- Complete chain-level sampler diagnostics.
- One freeze intervention only if the primary transition is clear and time remains.

## Why this scope

The structured-versus-shuffled comparison separates new lexical exposure from syntactic/compositional structure. Matched English separates language adaptation from generic continued training. A second Portuguese seed tests whether the headline is not a single-run accident. These are more valuable than adding many languages without controls.

## Main technical risk

Intermediate Portuguese checkpoints may not behave like local minima of the Portuguese empirical loss. A localized SGLD chain can drift downhill rather than equilibrate around the checkpoint. If no common localization/temperature configuration yields stable traces across early, middle, and late checkpoints, the intended LLC comparison is not valid. This is a go/no-go gate, not a plot-cleaning problem.

## Planning estimates before benchmarking

| Resource | Median | Subjective 80% planning interval |
|---|---:|---:|
| One final continued-pretraining trajectory | 15 minutes | 5–35 minutes |
| All training and learning-rate pilots | 1 GPU-hour | 0.4–2.5 |
| Sampler tuning and final LLC campaign | 5 GPU-hours | 2.5–11 |
| Total charged VM/GPU time | 7 hours | 4–14 |
| Human/agent engineering and analysis | 22 hours | 14–36 |
| GCP project cash outlay | $20 | $8–$50 |

These are Fermi estimates. Replace them with benchmark measurements before the final campaign.

## Cloud choice

Use a GCP `g2-standard-4` VM with one NVIDIA L4 and 24 GB GPU memory in a G2-capable US zone, initially `us-central1-a`. São Paulo GCP zones list T4 rather than G2. Use on-demand capacity for final runs. RunPod is a contingency if GCP quota or capacity becomes a blocker, but this handoff automates GCP because the operator already has billing configured.

## Codex architecture

Install Codex CLI on the remote GPU VM. Connect the Codex App through SSH remote projects, so Codex directly sees the remote filesystem and shell. Use local `gcloud` scripts only for VM lifecycle. Launch long runs independently of the SSH session through the bounded runner. Do not give the remote agent broad cloud IAM rights.

## Three decisive gates

1. **Infrastructure:** train-save-reload-sample works end to end and revised runtime is acceptable.
2. **Scientific pilot:** structured Portuguese improves, grammar probes pass sanity checks, shuffled control behaves differently, and one common sampler configuration works at three checkpoints.
3. **Final campaign:** only after the first two gates, run the 8M trajectories and reportable LLC estimates.

## Cautious success claim

A good result supports this statement:

> An estimated changepoint in local loss geometry aligned with the onset of held-out Portuguese grammatical generalization in a small-model continued-pretraining regime and was absent in matched controls.

It does not prove a universal language-learning phase transition, a formal Bayesian phase transition, or that LLC caused the capability.
