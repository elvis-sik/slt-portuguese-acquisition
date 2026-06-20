# Infrastructure Gate Report: infra_gate_20260620T050345Z

## Scope

Directive: rerun only the CUDA/infrastructure gate after operator-side driver repair. First perform a
non-mutating CUDA preflight; if CUDA is unavailable or `nvidia-smi` cannot communicate with the driver,
record a blocked diagnostic and stop without attempting pilot work.

## Commands

- `nvidia-smi`
- `python3 scripts/check_environment.py --output results/00_infrastructure_gate/infra_gate_20260620T050345Z/check_environment.json`
- `python3 scripts/estimate_project.py --train-benchmark results/00_infrastructure_gate/train_seq128.json --sampler-benchmark results/00_infrastructure_gate/sampler_smoke.json --hourly-rate-usd 1.00 --output-json results/00_infrastructure_gate/infra_gate_20260620T050345Z/project_estimate_from_previous_success.json --output-md results/00_infrastructure_gate/infra_gate_20260620T050345Z/project_estimate_from_previous_success.md`

No TinyStories-3M model loop, training benchmark, or devinterp sampler command was launched in this
rerun because the required preflight failed.

## Evidence

- `nvidia_smi.log`: `nvidia-smi` failed with exit code 9 and reported it could not communicate with
  the NVIDIA driver.
- `cuda_preflight.json`: `/usr/bin/python3` is available, but the active Python environment has no
  `torch`; the `nvidia-smi --query-gpu` probe failed with exit code 9.
- `check_environment.json`: system package probe found no `torch`, `transformers`, `datasets`,
  `devinterp`, `numpy`, or `pandas`; `nvidia-smi` returned exit status 9.
- `hardware_probe.log`: PCI still shows an NVIDIA 3D controller and NVIDIA kernel modules are loaded,
  but no `/dev/nvidia0` or `/dev/nvidiactl` compute/control device nodes were observed. The
  `check_environment.py` probe saw only `/dev/nvidia-caps`.

## Runtime And Cost

Incremental GPU-hours: 0.00. Incremental estimated cost: $0.00 at the repository planning assumption
of $1.00 per charged VM-hour. Commands were short diagnostics and did not launch GPU jobs.

The project estimator was rerun only against previous successful benchmark artifacts from
2026-06-20T01:43-01:49Z. That stale estimate remains 3.53 median charged hours and $3.53 raw compute
cost, with a 7.06 hour high sensitivity value. It is not a current gate pass.

## Failure Modes And Uncertainty

Primary blocker: driver/device availability in the current worker environment. The kernel module and
PCI device are visible, but `nvidia-smi` cannot communicate with the driver and the expected
compute/control device nodes are absent at probe time.

Secondary blocker: the active system Python environment is incomplete for the experiment stack. Even
after driver repair, the gate should verify that the intended Python environment exposes CUDA-enabled
PyTorch plus `transformers`, `datasets`, `devinterp`, `numpy`, and `pandas`.

## Gate Decision

Gate decision: stop.

Reason: the CUDA preflight failed before the infrastructure gate could validly launch the TinyStories-3M
loop, training benchmarks, or sampler smoke test.

Next bounded action: restore GPU device-node/driver availability from the operator side, activate or
repair the intended Python environment, verify `nvidia-smi` and PyTorch CUDA visibility in the exact
worker shell, then rerun only the infrastructure gate.
