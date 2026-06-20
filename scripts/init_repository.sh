#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ ! -d .git ]]; then
  git init
fi
if ! git config user.name >/dev/null; then git config user.name "Codex Handoff"; fi
if ! git config user.email >/dev/null; then git config user.email "codex-handoff@local.invalid"; fi
git add .
if ! git diff --cached --quiet; then
  git commit -m "Initialize SLT Portuguese research handoff"
else
  echo "No uncommitted initialization changes."
fi
