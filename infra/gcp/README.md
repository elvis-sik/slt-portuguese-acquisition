# GCP operator scripts

These scripts run on the local operator workstation, not inside the GPU worker.

- `provision_vm.sh`: dry-run by default; requires `CONFIRM_SPEND=YES`.
- `wait_for_gpu.sh`: waits through driver installation/reboot.
- `bootstrap_and_sync.sh`: installs basic tools, copies repository, installs Codex.
- `configure_ssh_for_codex.sh`: asks gcloud to create concrete OpenSSH entries.
- `start_vm.sh`, `stop_vm.sh`, `delete_vm.sh`: lifecycle operations.
- `download_results.sh`: retrieve the remote `results/` tree.

Review every command before execution. The scripts are examples and cannot detect organization-specific IAM, OS Login, firewall, or quota policy.
