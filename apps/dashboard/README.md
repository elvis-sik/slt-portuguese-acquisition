# Local Experiment Control Dashboard

Run from the repository root:

```bash
sfw pnpm install
pnpm dashboard:dev
```

The dashboard binds to `127.0.0.1:3000` by default. It reads the repository's `state/`
and `results/` trees, indexes them into `.dashboard/dashboard.sqlite`, and keeps real
artifacts as files.

## Control model

- VM lifecycle is limited to start, stop, status, and sync.
- Remote experiment commands are typed templates, not arbitrary shell from the browser.
- Pause/checkpoint/resume/fork write cooperative control JSON under `results/_control/`.
- Forking creates a new lineage request; it never overwrites an old run.

## Environment

The local worker reads `.env.local` by default. Useful overrides:

```bash
DASHBOARD_REPO_ROOT=/absolute/path/to/repo
DASHBOARD_ENV_FILE=/absolute/path/to/.env.local
DASHBOARD_SSH_HOST=slt-portuguese-l4.us-central1-a.elvis-launchpad
DASHBOARD_REMOTE_REPO_PATH=~/slt-portuguese
```

## Verification

```bash
pnpm dashboard:typecheck
pnpm dashboard:test
pnpm --dir apps/dashboard test:e2e
```
