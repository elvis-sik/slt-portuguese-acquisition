#!/usr/bin/env bash
# Resolve the OpenAI API key from 1Password and install it on the remote GPU VM
# so the Codex CLI can authenticate. The plaintext key is held in memory only,
# never written to a local file, and transmitted to the VM over SSH stdin (never
# as a command-line argument, which would be visible in `ps`).
#
# Operator configuration is read from the repository-root .env.local, which must
# contain the GCP coordinates plus a 1Password secret reference:
#
#   OPENAI_API_KEY_OP_REF=op://<vault>/<item>/<field>
#
# Prerequisites on the operator workstation:
#   - 1Password CLI (`op`) installed and signed in (`op signin` / desktop app integration).
#   - gcloud authenticated and able to SSH to the VM.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Operator config lives in the gitignored repo-root .env.local (override with ENV_FILE=...).
ENV_FILE="${ENV_FILE:-$ROOT/.env.local}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE. It must define PROJECT_ID, VM_NAME, ZONE, and OPENAI_API_KEY_OP_REF." >&2
  exit 2
fi
# shellcheck disable=SC1090
source "$ENV_FILE"

: "${PROJECT_ID:?PROJECT_ID is required in $ENV_FILE}"
: "${VM_NAME:?VM_NAME is required in $ENV_FILE}"
: "${ZONE:?ZONE is required in $ENV_FILE}"
: "${OPENAI_API_KEY_OP_REF:?OPENAI_API_KEY_OP_REF is required in $ENV_FILE (format: op://vault/item/field)}"

if [[ "$OPENAI_API_KEY_OP_REF" != op://* ]]; then
  echo "OPENAI_API_KEY_OP_REF must be a 1Password secret reference like op://Vault/Item/field." >&2
  echo "Got: $OPENAI_API_KEY_OP_REF" >&2
  exit 2
fi

if ! command -v op >/dev/null 2>&1; then
  echo "1Password CLI (op) not found. Install it and sign in, then re-run." >&2
  exit 3
fi

# Resolve the secret into a shell variable only. Never echo it, never write it locally.
echo "Reading $OPENAI_API_KEY_OP_REF from 1Password..."
OPENAI_API_KEY="$(op read --no-newline "$OPENAI_API_KEY_OP_REF")"
if [[ -z "$OPENAI_API_KEY" ]]; then
  echo "Resolved an empty secret from $OPENAI_API_KEY_OP_REF. Check the vault/item/field." >&2
  exit 4
fi
# Best-effort scrub on any exit path.
trap 'OPENAI_API_KEY=""; unset OPENAI_API_KEY' EXIT

REMOTE_ENV_REL=".config/slt-portuguese/codex.env"
echo "Installing key on $VM_NAME at ~/$REMOTE_ENV_REL (mode 600), via SSH stdin..."

# The key is piped to the remote command on stdin; the remote shell reads it into
# a variable and writes a 0600 env file outside the repo tree, then ensures
# interactive login shells source it. printf %q makes the stored value robust to
# any shell-special characters.
printf '%s\n' "$OPENAI_API_KEY" | gcloud compute ssh "$VM_NAME" \
  --project="$PROJECT_ID" --zone="$ZONE" --quiet --command='
    set -euo pipefail
    IFS= read -r KEY
    if [ -z "$KEY" ]; then echo "No key received on stdin." >&2; exit 1; fi
    umask 077
    ENVDIR="$HOME/.config/slt-portuguese"
    ENVF="$ENVDIR/codex.env"
    mkdir -p "$ENVDIR"
    printf "export OPENAI_API_KEY=%q\n" "$KEY" > "$ENVF"
    chmod 600 "$ENVF"
    # The Codex CLI (>=0.141) ignores the bare OPENAI_API_KEY env var for auth and needs an
    # explicit login that writes ~/.codex/auth.json. Register it here so a fresh bootstrap is
    # self-sufficient; otherwise codex exec returns 401 "Missing bearer authentication".
    if command -v codex >/dev/null 2>&1; then
      printf "%s" "$KEY" | codex login --with-api-key >/dev/null 2>&1 \
        && echo "Registered Codex API-key auth (~/.codex/auth.json)." \
        || echo "WARN: codex login --with-api-key failed; run it manually on the VM." >&2
    fi
    unset KEY
    MARK="# >>> slt-portuguese codex secret >>>"
    if ! grep -qF "$MARK" "$HOME/.bashrc" 2>/dev/null; then
      {
        echo "$MARK"
        echo "[ -f \"$HOME/.config/slt-portuguese/codex.env\" ] && . \"$HOME/.config/slt-portuguese/codex.env\""
        echo "# <<< slt-portuguese codex secret <<<"
      } >> "$HOME/.bashrc"
    fi
    echo "Wrote $ENVF and ensured ~/.bashrc sources it."
  '

# Verify the key is loadable on the remote without ever printing it.
echo "Verifying on the VM (length only, value is never printed)..."
gcloud compute ssh "$VM_NAME" \
  --project="$PROJECT_ID" --zone="$ZONE" --quiet --command='
    set -euo pipefail
    . "$HOME/.config/slt-portuguese/codex.env"
    if [ -n "${OPENAI_API_KEY:-}" ]; then
      echo "OK: OPENAI_API_KEY present on VM (length ${#OPENAI_API_KEY})."
    else
      echo "FAILED: OPENAI_API_KEY not set after sourcing codex.env." >&2
      exit 1
    fi
  '

echo
echo "Done. The Codex CLI will pick up OPENAI_API_KEY in interactive remote sessions."
echo "For non-interactive 'codex exec', codex/run_phase.sh sources ~/.config/slt-portuguese/codex.env automatically."
echo "To rotate the key: update the 1Password item and re-run this script."
