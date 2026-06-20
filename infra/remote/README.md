# Remote job utilities

Run these on the GPU VM. `run_bounded_job.sh` detaches a command, enforces a wall-clock timeout, captures output, and optionally shuts down the VM. It is a minimal safety wrapper, not a cluster scheduler.

Example:

```bash
infra/remote/run_bounded_job.sh --name sampler_grid --max-hours 2 --auto-stop-vm no -- \
  python -m experiments.sampler_sweep --config configs/sampler_sweep.yaml
infra/remote/job_status.sh sampler_grid
```
