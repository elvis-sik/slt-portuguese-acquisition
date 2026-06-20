# Benchmarks and Fermi estimates

## Why benchmark first

Tiny models do not necessarily achieve high hardware utilization. Python overhead, data loading, checkpoint writes, observer evaluations, and many small kernels can dominate. FLOP-only estimates are therefore less trustworthy than two short end-to-end measurements.

## Benchmark A: ordinary training

For sequence lengths 64 and 128:

1. use the real model, optimizer, precision, and data collator;
2. run 50 unmeasured warm-up steps;
3. time 200 steps with GPU synchronization;
4. record mean, median, p95, tokens/second, peak VRAM, CPU utilization, and checkpoint-write time;
5. repeat once if coefficient of variation exceeds 10%.

The included `scripts/benchmark_train.py` provides a kernel/data smoke benchmark. Once the actual data loader exists, Codex must repeat the measurement through the real training entry point.

## Benchmark B: sampler

At one pilot checkpoint:

1. use the actual fixed sampling dataset and observables;
2. run two chains;
3. use 100 burn-in steps and 50–100 draws;
4. include intended draw spacing;
5. record wall time, approximate chain-step count, peak VRAM, and output size;
6. save raw traces and inspect them; performance without validity is not a pass.

The included `scripts/benchmark_sampler.py` is an API/performance smoke test, not a scientifically valid LLC estimate when used with random tokens.

## Step-count model

For 8 million target tokens, sequence length 128, and global batch 32:

\[
N_{\text{steps/run}} = \frac{8,000,000}{128\times 32} \approx 1,953.
\]

Four final trajectories require about 7,812 optimizer steps. Add roughly 2,500 steps for pilots, LR trials, failed starts, and one optional branch:

\[
N_{\text{train}} \approx 10,000.
\]

Illustrative sampler allocation:

| Component | Approx. chain steps |
|---|---:|
| 27-setting coarse sweep | 4,000 |
| early/middle/late cross-check | 4,500 |
| main seed A | 8,400 |
| main seed B | 4,000 |
| two controls | 4,800 |
| transition-region extra chains | 4,000 |
| null/noise diagnostics | 2,000 |
| **Total** | **31,700** |

## Project runtime equation

Let `t_train` and `t_sampler` be measured seconds per ordinary and per chain step. A planning estimate is:

\[
H = 1.4\left(
\frac{N_{\text{train}}t_{\text{train}}}{3600}+
\frac{N_{\text{sampler}}t_{\text{sampler}}}{3600}
\right)+H_{\text{evaluation}}.
\]

The factor 1.4 covers routine orchestration/I/O overhead. Add evaluation/report time separately. Use the included estimator:

```bash
python scripts/estimate_project.py \
  --train-benchmark results/00_infrastructure_gate/train_seq128.json \
  --sampler-benchmark results/00_infrastructure_gate/sampler_smoke.json \
  --hourly-rate-usd 1.00 \
  --output-json results/00_infrastructure_gate/project_estimate.json \
  --output-md results/00_infrastructure_gate/project_estimate.md
```

## Pre-benchmark planning distribution

Assumed L4 timings:

```text
ordinary training step: 0.08–0.40 s
sampler chain step:     0.15–0.80 s
```

These deliberately broad ranges yield:

- ordinary training: 0.2–1.1 GPU-hours;
- raw sampler stepping: 1.3–7.0 GPU-hours;
- evaluation, I/O, failed settings, and idle overhead: 1.5–5 hours;
- total midpoint around 7 charged hours;
- subjective 80% interval around 4–14 hours.

One 8M training trajectory should generally be minutes, not ten hours. A ten-hour single trajectory is a signal that the pipeline/model choice is wrong for this sprint.

## Dollar model

Exact GCP G2 pricing depends on region and current billing configuration. This handoff uses a **user-editable planning assumption** of $1.00 per charged VM-hour. It is not an official quote. Confirm the console price before provisioning.

At 7 hours, raw planned compute is about $7. Real project cost is higher because of driver/bootstrap time, sampler failures, idle time, disk, and contingency. Budget:

| Level | Amount | Meaning |
|---|---:|---|
| Expected working spend | $20 | likely full project with ordinary iteration |
| Soft review threshold | $35 | require explicit rescope decision |
| Hard project cap | $50 | do not cross without human approval |

GCP budget alerts do not themselves hard-stop spending. Use job timeouts, automatic shutdown after long jobs, manual lifecycle scripts, and a human gate.

## Sensitivity rules

If median projected charged time exceeds 10 hours:

- reduce LLC checkpoint density;
- retain both controls and diagnostic chains;
- reduce second-seed sampling before first-seed sampling;
- remove optional intervention and Spanish;
- consider sequence length 64 if the scientific probe remains valid;
- do not use fewer than two chains for a reported estimate.

If the 80% upper estimate exceeds 18 hours or $50, pivot to the controlled micro-language primary experiment.

## What the estimate excludes

- paid machine translation;
- Codex/OpenAI usage charges;
- human labor;
- unavailable-capacity delays;
- data egress beyond ordinary small artifacts;
- an A100 or multi-GPU environment, which is not recommended here.
