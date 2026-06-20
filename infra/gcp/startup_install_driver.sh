#!/usr/bin/env bash
set -euxo pipefail
MARKER_DIR=/opt/google/cuda-installer
mkdir -p "$MARKER_DIR"
cd "$MARKER_DIR"
if nvidia-smi >/dev/null 2>&1; then
  touch driver_ready
  exit 0
fi
curl -fSsL -o cuda_installer.pyz \
  https://storage.googleapis.com/compute-gpu-installation-us/installer/latest/cuda_installer.pyz
python3 cuda_installer.pyz install_driver --installation-mode=repo --installation-branch=prod || true
# Google's installer may reboot the VM. On the next startup this script runs again.
if nvidia-smi >/dev/null 2>&1; then
  touch driver_ready
fi
