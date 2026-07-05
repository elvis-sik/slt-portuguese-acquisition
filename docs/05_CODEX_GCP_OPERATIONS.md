# Codex and GCP operations

> Status, 2026-06-21: operator reference, not judge-facing evidence. Secrets and local operator config are
> intentionally outside Git.

## Direct answer

Yes. Codex can work on the GCP instance over SSH. The most robust arrangement is to install Codex CLI on the GPU VM and connect the desktop Codex App to that SSH host as a remote project. OpenAI documents that remote project threads run commands and read/write files on the remote host, and that the remote host must have the `codex` command on its login-shell `PATH`.

You do not need to build a custom “Codex image” or expose a Codex server to the internet. A normal Ubuntu VM, Codex CLI installation, SSH key, and repository are sufficient. The Codex App starts its remote app server through SSH. Do not expose that app-server transport directly.

## Recommended split of authority

### Local operator plane

The local workstation holds `gcloud` credentials and controls:

- create/start/stop/delete VM;
- GCP project and quota;
- budget review;
- initial SSH configuration;
- final artifact download.

All spend-affecting scripts default to dry-run or require explicit confirmation.

### Remote worker plane

The GCP VM holds:

- Codex CLI and remote repository;
- Python environment and model/data cache;
- GPU jobs;
- checkpoints, traces, logs, figures, and run manifests.

The worker should have no broad GCP IAM permissions. Codex can be granted broad filesystem/process access inside a disposable worker when genuinely required, without granting authority over the cloud account.

## Three workable control modes

### 1. Codex App SSH remote project — recommended

1. Configure a concrete host alias in local `~/.ssh/config`.
2. Confirm `ssh <alias>` works.
3. Install and authenticate Codex on the VM.
4. Add the host under Codex App settings and select the remote repository.

This provides the best iterative experience because the agent’s shell and files are already on the GPU host.

### 2. SSH into the VM and run Codex CLI

This is the fallback when the desktop remote-project UI is unavailable:

```bash
ssh slt-gpu
cd ~/slt-portuguese
codex
```

### 3. Noninteractive `codex exec`

Use for bounded, structured phases after the repository is stable:

```bash
./codex/run_phase.sh codex/prompts/01_scientific_pilot.md
```

OpenAI documents `codex exec` for scripted/CI-like work and supports JSONL/structured output. The wrapper defaults to workspace-write permissions and requires explicit confirmation for danger-full-access.

## Why not only run Codex locally and call `gcloud compute ssh --command` repeatedly?

It is possible, and the included local scripts use `gcloud` for lifecycle and bootstrap. It is weaker as the main research loop because:

- shell state is fragmented;
- remote file edits and log inspection are awkward;
- long commands are tied to connection behavior unless detached carefully;
- model/data cache and environment context are less visible;
- quoting and file-transfer failures consume hackathon time.

Use local Codex for documentation and infrastructure scripts. Use remote Codex for GPU experimentation.

## Long-running jobs

A Codex or SSH session is not a job scheduler. Launch every long experiment with:

```bash
infra/remote/run_bounded_job.sh \
  --name pt_seed_a \
  --max-hours 2 \
  --auto-stop-vm no \
  -- python -m experiments.train --config configs/final_pt_seed_a.yaml
```

The runner detaches the process, applies a timeout, captures logs/status, and can shut down the VM at completion. Monitor with `infra/remote/job_status.sh`.

Do not rely on Codex remaining connected. A detached job can continue, but Codex will not autonomously resume analysis after a disconnected session unless a separate orchestrator is explicitly running.

## Autonomy policy

Codex may iterate without supervision inside a bounded phase when all of these are true:

- maximum runtime and incremental cost are declared;
- the experiment belongs to a frozen search space;
- automatic stop conditions exist;
- outputs and failed traces are retained;
- the phase cannot provision or resize infrastructure;
- the result cannot directly publish or alter the hypothesis.

Appropriate autonomous tasks include code fixes, short benchmark reruns, a predeclared LR grid, and a predeclared sampler grid.

Human gates remain appropriate for final-run launch, budget expansion, scientific scope changes, and publication.

## Permissions

Start with Codex workspace-write permissions. Network/model download and system package installation may require approvals. `danger-full-access` is acceptable only on the isolated worker, and only when the remote VM lacks valuable credentials and the command is bounded. The wrapper refuses it unless `CONFIRM_DANGER=YES` is set.

Do not place GCP owner/editor credentials, service-account keys, billing credentials, or long-lived secrets in the repository or remote environment. Treat `~/.codex/auth.json` as a secret.

## Is the local machine enough?

The local machine is sufficient for report writing, data filtering prototypes, unit tests, and tiny CPU smoke tests. The final campaign benefits materially from a GPU because full-parameter training is repeated and SGLD requires tens of thousands of gradient-equivalent steps. A CPU-only run may be technically possible for 3M parameters but is a poor use of a three-day sprint.
