# SLT Portuguese adaptation: Codex handoff

This repository is a practical handoff for a three-day research sprint studying whether an SLT-derived measure changes when a small English-trained language model acquires Portuguese.

**The report under `reference/mock_report/` is synthetic. Every result, model run, effect size, confidence interval, changepoint, and intervention in it was fabricated for planning. Never mix those files with empirical results.**

## Recommended operating model

Use a dedicated GCP GPU VM as the worker. Install Codex CLI on that VM, place this repository there, and connect the desktop Codex App through its SSH remote-project feature. Provisioning, stopping, and deleting the VM stay on the local operator side and require explicit confirmation. Long model jobs are launched with a bounded detached runner, so loss of an SSH or Codex session does not terminate them.

```text
local workstation                         GCP GPU VM
-----------------                         ----------
Codex App  -- SSH remote project ------>  Codex CLI + repository
local gcloud scripts ------------------->  start/stop/provision only
human approval gates                      bounded training/SGLD jobs
                                           logs + checkpoints + manifests
```

This is preferable to asking a local agent to issue many one-off `gcloud compute ssh --command ...` calls. It preserves remote state, makes logs and files directly visible to Codex, and follows OpenAI's documented remote-connection workflow.

## Start here

1. Read `START_HERE_FOR_CODEX.md` and `AGENTS.md`.
2. Read `docs/00_EXECUTIVE_PLAN.md` and `docs/03_THREE_DAY_EXECUTION_PLAN.md`.
3. Copy `infra/gcp/env.example` to `infra/gcp/.env` and fill in the GCP project ID.
4. Validate the local bundle:

   ```bash
   python scripts/validate_handoff.py
   ```

5. Dry-run VM creation:

   ```bash
   DRY_RUN=1 ./infra/gcp/provision_vm.sh
   ```

6. Create the VM only after inspecting the command:

   ```bash
   CONFIRM_SPEND=YES DRY_RUN=0 ./infra/gcp/provision_vm.sh
   ```

7. Wait for the startup driver installation and possible reboot, then verify and bootstrap:

   ```bash
   ./infra/gcp/wait_for_gpu.sh
   ./infra/gcp/bootstrap_and_sync.sh
   ./infra/gcp/configure_ssh_for_codex.sh
   ```

8. In the Codex App, add the concrete SSH host printed by the last command and choose the remote repository folder.
9. On the remote VM, run the infrastructure gate before any scientific run:

   ```bash
   make check-env
   make benchmark-train
   make benchmark-sampler
   ```

The exact experiment implementation is intentionally not falsely presented as complete. The repository contains protocols, benchmark utilities, safety rails, prompts, templates, and a synthetic reference report. Codex should implement and test the real data/training/evaluation pipeline under the gates in `AGENTS.md`.

## Key documents

- `docs/01_RESEARCH_PROTOCOL.md`: scientific design and claims.
- `docs/02_SLT_BAYESIAN_COMPLICATIONS.md`: why LLC estimation is not merely a callback.
- `docs/04_BENCHMARKS_AND_FERMI_ESTIMATES.md`: time and dollar model.
- `docs/05_CODEX_GCP_OPERATIONS.md`: remote Codex architecture and autonomy.
- `docs/07_ADAPTION_AUTOSCIENTIST_ASSESSMENT.md`: qualification test for Adaption.
- `docs/09_FAKE_REPORT_WALKTHROUGH.md`: page-by-page reading of the mock report.
- `reference/mock_report/README_BUILD.md`: reproduce the synthetic figures and rebuild the static report template.

## Current planning envelope

Before a real benchmark, the planning estimate is approximately 7 charged GPU-hours, with a subjective 80% interval of 4–14 hours. At a user-supplied planning rate of $1.00 per VM-hour, the raw compute midpoint is about $7. Including setup, failed sampler settings, idle time, storage, and one partial rerun, reserve $20 and impose a $50 hard project budget. These are engineering estimates, not statistical confidence intervals and not an official GCP quote.

## Repository status

This handoff was assembled on 2026-06-20. External services, package APIs, GPU availability, and prices can change. Verify them at execution time. See `docs/SOURCES.md`.
