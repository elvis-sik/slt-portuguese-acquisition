# Codex workflow

The preferred interface is an interactive Codex App thread connected to the remote SSH project. The prompt files are also usable with `codex exec` for structured, bounded phases.

```bash
./codex/run_phase.sh codex/prompts/00_infrastructure_gate.md
```

The wrapper writes a JSONL event log and a final structured decision. It defaults to `workspace-write`. Set `CODEX_SANDBOX=danger-full-access CONFIRM_DANGER=YES` only on the isolated worker when system-level access is genuinely necessary.

Do not use `codex exec` as the long-running training process. Codex should launch the actual experiment through `infra/remote/run_bounded_job.sh`, then inspect its logged output.
