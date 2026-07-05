# SLT and Bayesian complications

> Status, 2026-06-21: historical planning document. It explains why LLC measurement is delicate; current
> results and limitations are summarized in `PROJECT_STATUS.md` and `reports/`.

## What changes and what does not

The continued-pretraining optimizer remains ordinary AdamW. SLT enters through a second procedure that samples a localized posterior around selected checkpoints. In schematic form:

\[
p(w\mid w_0) \propto
\exp[-n\beta L_n(w)]
\exp[-2\gamma\lVert w-w_0\rVert^2],
\]

where the checkpoint is the center, the empirical loss and reference dataset define the measured geometry, `n_beta` controls effective inverse temperature, and localization controls how far the sampler can move.

Therefore, the project does not need Bayesian neural-network pretraining from scratch. It does need a measurement design that makes localized posterior estimates comparable.

## Why calling `llc()` is not enough

### Intermediate checkpoints may not be local minima

The clean theoretical object is associated with local geometry near minima of a population loss. A checkpoint halfway through Portuguese adaptation can have an obvious downhill direction on Portuguese loss. A localized chain can therefore drift toward a better point rather than equilibrate around the checkpoint.

Inspect whether sampled loss rises from the baseline, reaches a stable range, and remains localized. Persistent loss below the center or monotonic downhill movement is a rejection signal. Increasing localization or adjusting effective temperature may help, but a checkpoint that never admits a stable common protocol should not produce a headline LLC number.

### The dataset is part of the measurement

LLC is not a context-free scalar attached to weights. The sampling dataset, loss, normalization, temperature, localization, and parameterization matter. Use fixed reference sets and compare trajectories within condition. Normalize raw LLC within run for visualization if necessary, but retain raw estimates and settings.

### Hyperparameter selection is a scientific degree of freedom

The three primary knobs are sampler learning rate, `n_beta`, and localization. Burn-in, draw spacing, chain count, draw count, batch size, and preconditioner also matter. A configuration that looks good at one checkpoint may fail elsewhere.

Use this staged procedure.

#### Coarse sweep on one middle checkpoint

Start with:

```text
learning rate ∈ {1e-6, 1e-5, 1e-4}
n_beta        ∈ {1, 10, 100}
localization  ∈ {10, 100, 1000}
```

Use short one-chain traces only to eliminate explosions, zero signal, and obvious drift. These are starting scales from current Timaeus guidance, not universally correct values.

#### Cross-check across trajectory

Take the two or three most plausible configurations and test each at early, middle, and late checkpoints using two chains and longer traces.

Select one global configuration based on explicit criteria:

- no NaNs or spikes;
- chain losses plateau after burn-in;
- no persistent downhill movement below baseline;
- nontrivial signal relative to stochastic noise;
- chains broadly agree;
- parameter displacement remains local;
- behavior is acceptable at all three checkpoints.

#### Final campaign

An initial reportable allocation is:

```text
num_chains            = 3
num_burnin_steps      = 200
num_draws             = 100
num_steps_between     = 2
```

This is about 400 chain steps per chain under one common interpretation. Increase chains or draws near the headline interval if between-chain dispersion is high. Do not reduce to one chain to save the project.

## Autocorrelation and uncertainty

SGLD samples are autocorrelated. Thinning is not a substitute for diagnosis. Plot autocorrelation or estimate an effective sample size, inspect running means, and compare independent chains. A narrow standard error calculated from highly correlated draws is misleading.

Separate uncertainty sources:

- within-chain Monte Carlo uncertainty;
- between-chain uncertainty;
- seed-to-seed training variation;
- evaluation-item bootstrap uncertainty;
- changepoint uncertainty due to checkpoint spacing;
- sampler-hyperparameter sensitivity.

Do not collapse all of these into one decorative error bar.

## Objective mismatch

If training uses weight decay but the sampling loss omits it, or training uses one reduction and the sampler another, the local object changes. For the cleanest first run, use zero weight decay and match next-token cross-entropy exactly. Record whether padding tokens and sequence boundaries are masked identically.

## Parameterization and LoRA

SLT quantities can depend on parameterization in finite empirical settings. Adapter-only training constrains the path to a low-dimensional subspace. An adapter-only LLC then characterizes that adapter parameterization; a full-model LLC around a mostly frozen network answers another question. Use full-parameter training for the primary study.

## Precision

Small Langevin updates and injected noise make numerical behavior important. Begin with FP32 sampling. BF16 training is acceptable only if it materially improves benchmark time and produces equivalent short-pilot behavior. Keep an FP32 copy of checkpoints for sampling when feasible.

## Nonstationarity and claims

A training-trajectory changepoint in an estimated LLC is not automatically a formal Bayesian phase transition. Use cautious terms:

- acceptable: “LLC changepoint,” “local geometric reorganization,” “SLT-derived diagnostic”;
- avoid without stronger evidence: “proved phase transition,” “the model crossed a singularity,” “Portuguese grokking.”

A theory-faithful phase-diagram study would vary effective sample size or temperature and examine posterior competition across equilibrated regions. That is outside this weekend scope.

## Computational consequence

A sampler step is roughly a training-like gradient step, but the campaign multiplies steps by chains, checkpoints, and tuning configurations. A plausible campaign contains about 31,700 chain steps versus about 10,000 ordinary training/pilot steps. SGLD is therefore likely to dominate cost even though the model is tiny.
