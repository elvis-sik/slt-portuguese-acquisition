# Go/no-go checklist

## Infrastructure gate

- [ ] `nvidia-smi` shows the expected GPU.
- [ ] `torch.cuda.is_available()` is true.
- [ ] model forward/backward works.
- [ ] training checkpoint saves and reloads.
- [ ] `devinterp` imports and accepts the model/dataset.
- [ ] two sampler chains complete without NaNs/OOM.
- [ ] peak VRAM has at least 25% headroom.
- [ ] benchmark JSONs and logs are saved.
- [ ] revised median charged runtime ≤10 hours.
- [ ] projected pre-contingency spend ≤$35.

## Scientific pilot gate

- [ ] data split hashes are frozen.
- [ ] no train/eval leakage found.
- [ ] Portuguese BPB improves.
- [ ] grammar scoring passes known-good sanity checks.
- [ ] continuous grammar margins are stored, not only accuracy.
- [ ] structured Portuguese differs from shuffled control.
- [ ] English-retention metric works.
- [ ] one sampler configuration works at early/middle/late checkpoints.
- [ ] all failed traces are retained.
- [ ] final checkpoint schedule and adaptive rule are timestamped.

## Final campaign gate

- [ ] final configs are committed.
- [ ] expected incremental hours/cost are recorded.
- [ ] human approval for final run is recorded.
- [ ] every long command has a timeout.
- [ ] checkpoints and logs have sufficient disk space.
- [ ] VM auto-stop or operator stop plan is set.

## Report gate

- [ ] every number traces to a real run ID.
- [ ] mock-report files are not referenced as evidence.
- [ ] chain-level diagnostics are included.
- [ ] uncertainty source is stated for every interval.
- [ ] controls are shown in the same figure/table.
- [ ] claim language does not overstate phase transition or causality.
- [ ] limitations include transient-checkpoint/local-minimum issue.
- [ ] code, configs, hashes, and evaluation set are packaged.
