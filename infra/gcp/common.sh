#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-$SCRIPT_DIR/.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE. Copy env.example to .env and edit it." >&2
  exit 2
fi
# shellcheck disable=SC1090
source "$ENV_FILE"
: "${PROJECT_ID:?PROJECT_ID is required}"
: "${VM_NAME:?VM_NAME is required}"
: "${ZONE:?ZONE is required}"
: "${MACHINE_TYPE:?MACHINE_TYPE is required}"
: "${BOOT_DISK_GB:?BOOT_DISK_GB is required}"
REMOTE_REPO_DIR="${REMOTE_REPO_DIR:-slt-portuguese}"
IMAGE_FAMILY="${IMAGE_FAMILY:-ubuntu-2204-lts-amd64}"
IMAGE_PROJECT="${IMAGE_PROJECT:-ubuntu-os-cloud}"
