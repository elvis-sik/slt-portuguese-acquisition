#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"
DRY_RUN="${DRY_RUN:-1}"
CONFIRM_SPEND="${CONFIRM_SPEND:-NO}"

cmd=(gcloud compute instances create "$VM_NAME"
  --project="$PROJECT_ID"
  --zone="$ZONE"
  --machine-type="$MACHINE_TYPE"
  --provisioning-model=STANDARD
  --boot-disk-type=pd-balanced
  --boot-disk-size="${BOOT_DISK_GB}GB"
  --image-family="$IMAGE_FAMILY"
  --image-project="$IMAGE_PROJECT"
  --maintenance-policy=TERMINATE
  --restart-on-failure
  --metadata-from-file="startup-script=$SCRIPT_DIR/startup_install_driver.sh"
  --labels="project=slt-portuguese,managed-by=handoff"
)
if [[ -n "${SERVICE_ACCOUNT:-}" ]]; then
  cmd+=(--service-account="$SERVICE_ACCOUNT")
else
  cmd+=(--no-service-account)
fi

printf 'Command to run:\n'
printf ' %q' "${cmd[@]}"
printf '\n'

if [[ "$DRY_RUN" != "0" || "$CONFIRM_SPEND" != "YES" ]]; then
  echo "Dry run only. Set DRY_RUN=0 CONFIRM_SPEND=YES to create the paid VM."
  exit 0
fi

"${cmd[@]}"
echo "Created $VM_NAME in $ZONE. Driver installation may reboot it."
echo "Next: $SCRIPT_DIR/wait_for_gpu.sh"
