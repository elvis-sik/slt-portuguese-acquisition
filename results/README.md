# Real results only

This tree is reserved for empirical benchmark and experiment outputs. Do not copy synthetic artifacts here.

The GitHub-facing tree keeps compact, inspectable summaries: manifests, frozen configs, source tables,
small JSON metrics, and phase reports. Heavy checkpoints, zarr traces, tokenized corpora, operational
Codex transcripts, and bounded-job runner logs are intentionally ignored or removed from Git. They are
operator/provenance artifacts rather than judge-facing evidence.

Current narrative summaries live in:

- `../PROJECT_STATUS.md`
- `../FUTURE_WORK.md`
- `../reports/seed_a_llc_trajectory/REPORT.md`
- `../reports/control_comparison/REPORT.md`

Exploratory low-resource guardrail outputs under `mrguard/` and `sw_guardrail_pod/` are preserved as
future-work material. They are not part of the primary SLT-Portuguese submission claim.
