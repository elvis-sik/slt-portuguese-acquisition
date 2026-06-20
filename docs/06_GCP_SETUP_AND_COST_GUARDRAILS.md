# GCP setup and cost guardrails

## Recommended instance

```text
machine type: g2-standard-4
GPU:          1 × NVIDIA L4, 24 GB
vCPUs:        4
system RAM:   16 GB
boot disk:    100 GB pd-balanced
OS:           Ubuntu 22.04 LTS
zone:         us-central1-a initially
provisioning: STANDARD/on-demand
```

G2 does not support Deep Learning VM images as boot disks, so this handoff uses Ubuntu and Google's documented driver installer. The driver startup script may reboot the instance. Wait for `nvidia-smi` before bootstrapping Python.

G2 is available in several US zones. São Paulo currently lists N1+T4 rather than G2; network latency is not material after data/models are cached.

## Local prerequisites

- Google Cloud CLI authenticated to the intended account;
- Compute Engine API enabled;
- GPU quota for G2/L4 in the selected region;
- an SSH key managed by `gcloud` or OS Login;
- a reviewed GCP console price;
- a billing budget alert, recognizing that alerts are not hard caps.

## Provisioning

```bash
cp infra/gcp/env.example infra/gcp/.env
$EDITOR infra/gcp/.env
DRY_RUN=1 ./infra/gcp/provision_vm.sh
CONFIRM_SPEND=YES DRY_RUN=0 ./infra/gcp/provision_vm.sh
```

The script uses standard capacity, `pd-balanced`, Ubuntu 22.04, maintenance termination, restart on failure, and a startup script that installs the GPU driver. It attempts to create the VM without a service account. If organization policy requires one, create a dedicated service account with no project roles and set it explicitly rather than attaching a broad default account.

## Driver installation

Google's current installer is downloaded from:

```text
https://storage.googleapis.com/compute-gpu-installation-us/installer/latest/cuda_installer.pyz
```

The startup script installs the production-branch driver. It does not install the full CUDA toolkit because PyTorch wheels normally provide the user-space runtime needed for this workload. Install the toolkit only if a package actually requires `nvcc`.

## Cost controls

1. Confirm the console hourly price before creation.
2. Keep `HOURLY_RATE_USD` in `.env` current.
3. Use `run_bounded_job.sh` for every long job.
4. Use `--auto-stop-vm yes` for unattended final jobs when no immediate follow-up is needed.
5. Stop the VM when analyzing/reporting locally.
6. Persist small results to the boot disk and download them before deletion.
7. Do not use Spot for final runs unless explicitly approved.
8. Review `gcloud compute instances describe` before leaving the VM unattended.

The repository's $50 cap is a project rule, not a GCP-enforced hard limit.

## Capacity fallback

Try `us-central1-a`, then `us-central1-b`, `us-central1-c`, `us-east1-b`, or another documented G2 zone. Do not spend more than roughly 30 minutes fighting quota/capacity. The operational fallback is a rented 24 GB GPU provider; the scientific pipeline should remain provider-neutral.

## Lifecycle

```bash
./infra/gcp/start_vm.sh
./infra/gcp/stop_vm.sh
CONFIRM_DELETE=YES ./infra/gcp/delete_vm.sh
```

Deletion is intentionally gated. Download `results/`, Git commits, environment lock, and checkpoint hashes first.
