# LLC Campaign Phase Report

- Run ID: `llc_campaign_final_training_20260620T053855Z`
- Source final run: `results/02_final_training/final_training_20260620T053855Z`
- Primary condition: `structured_pt_seed_a`
- Frozen selected tokens: `[0, 100000, 400000, 1500000, 5000000, 8000000]`
- Gate decision: `llc_complete_with_rejections`

## Evidence

- Manifest: `results/03_llc_campaign/llc_campaign_final_training_20260620T053855Z/manifest.json`
- Campaign summary: `results/03_llc_campaign/llc_campaign_final_training_20260620T053855Z/llc_campaign_summary.json`
- Checkpoint validation: `results/03_llc_campaign/llc_campaign_final_training_20260620T053855Z/checkpoint_validation.json`
- Raw traces: `results/03_llc_campaign/llc_campaign_final_training_20260620T053855Z/raw_traces`
- Running estimates: `results/03_llc_campaign/llc_campaign_final_training_20260620T053855Z/running_estimates`
- Parameter displacement: `results/03_llc_campaign/llc_campaign_final_training_20260620T053855Z/displacement`
- Failures: `results/03_llc_campaign/llc_campaign_final_training_20260620T053855Z/failures`
- Report-source tables: `results/03_llc_campaign/llc_campaign_final_training_20260620T053855Z/report_source_tables`

## Sampler Controls

- One global sampler configuration was used for every selected checkpoint.
- Sampler config: `{'precision': 'fp32', 'full_parameter_sampling': True, 'sampling_method': 'sgmcmc_sgld', 'lr': 1e-05, 'n_beta': 10.0, 'localization': 100.0, 'batch_size': 32, 'num_chains': 3, 'num_burnin_steps': 200, 'num_draws': 100, 'num_steps_bw_draws': 2, 'save_metrics': True, 'init_seed': 20260620, 'match_sampling_input_ids_across_chains': True, 'shuffle': True}`
- Reference set: `results/02_final_training/final_training_20260620T053855Z/data_splits/sampler_reference.jsonl`
- Reference hash: `b9a366d668658bb1d8fda5143aeae70c3c08b439ac10bb34fc33966fc5e4752f`
- Sequence length: `128`
- Loss/normalization: devinterp next-token cross-entropy with fixed sequence length; raw LLC retained.

## Diagnostics

- Reportable checkpoints with diagnostics: `0`
- Rejected selected checkpoints: `0`
- Invalid/missing selected checkpoints: `0`

## Runtime And Cost

- Wall seconds: `7.13`
- Estimated GPU-hours: `0.0020`
- Projected total cost USD: `$0.2496`
- Hard cap USD: `$50.00`

## Uncertainty

- Chain diagnostics, running estimates, displacement, and raw zarr traces are required for interpretation.
- Rejected checkpoints must not be collapsed into a headline scalar.
- This report does not claim a formal SLT phase transition.

## Failure Modes

- Intermediate checkpoints can drift downhill under the localized sampler.
- Between-chain dispersion and autocorrelation can make scalar LLC overconfident.
- The result is conditional on the fixed reference set and sampler configuration.

## Gate Decision

`llc_complete_with_rejections`. Next bounded action: Build the real report from report-source tables and raw diagnostics.
