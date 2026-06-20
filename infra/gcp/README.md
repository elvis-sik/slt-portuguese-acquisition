# GCP operator scripts

These scripts run on the local operator workstation, not inside the GPU worker.

- `provision_vm.sh`: dry-run by default; requires `CONFIRM_SPEND=YES`.
- `wait_for_gpu.sh`: waits through driver installation/reboot.
- `bootstrap_and_sync.sh`: installs basic tools, copies repository, installs Codex, and (if configured) pushes the Codex API key.
- `push_codex_secret.sh`: resolves the OpenAI API key from 1Password (`OPENAI_API_KEY_OP_REF` in `.env.local`) and installs it on the VM at `~/.config/slt-portuguese/codex.env` (mode 600). The plaintext is held in memory only and sent over SSH stdin — never written locally, never passed as an argument. Re-run to rotate the key.
- `configure_ssh_for_codex.sh`: asks gcloud to create concrete OpenSSH entries.
- `start_vm.sh`, `stop_vm.sh`, `delete_vm.sh`: lifecycle operations.
- `download_results.sh`: retrieve the remote `results/` tree.

Review every command before execution. The scripts are examples and cannot detect organization-specific IAM, OS Login, firewall, or quota policy.
