# Revised project estimate

Status: stale previous-success estimate. The current run `infra_gate_20260620T050345Z` stopped before fresh
benchmarks because `nvidia-smi` exited 9, so this is not evidence for a current infrastructure pass.
Inputs are top-level benchmark JSONs from 2026-06-20T01:43-01:49Z.

- Training step: 0.0751 s
- Sampler chain step: 0.1411 s
- Charged hours: 2.12 / **3.53** / 7.06 (low/median/high)
- Raw compute cost at $1.00/h: $2.12 / **$3.53** / $7.06
- Review required: False

This is a sensitivity range, not a statistical confidence interval. Add setup, disk, failed runs, and contingency to the cash budget.
