import { getMeta, setHealth, setMeta } from "@/lib/db";
import { refreshIndex } from "@/lib/indexer";
import { enqueueAction, executePendingActions } from "@/lib/actions";
import { getConfig, repoPath } from "@/lib/paths";
import { safeReadJson } from "@/lib/files";
import { runCommand } from "@/lib/commands";

const SHUTDOWN_STATUSES = new Set([
  "complete",
  "halted_deadline",
  "halted_budget",
  "halted_operator"
]);

// When the orchestrator reaches a terminal state with request_shutdown, do one final sync and
// stop (never delete) the VM — operator-side, so cloud lifecycle stays off the worker per AGENTS.md.
async function maybeAutoStopOnComplete(vmStatus: string | null): Promise<void> {
  if (vmStatus !== "RUNNING") return;
  const state = safeReadJson(repoPath("results", "_orchestrator", "state.json")) as
    | Record<string, unknown>
    | null;
  if (!state) return;
  const status = String(state.status ?? "");
  const requestShutdown = state.request_shutdown === true;
  const autoStop = state.auto_stop_on_complete === true;
  if (!requestShutdown || !autoStop || !SHUTDOWN_STATUSES.has(status)) return;
  const token = `${state.started_at ?? ""}:${status}`;
  if (getMeta<string | null>("orchestrator_autostop", null) === token) return; // already handled
  await syncSmallArtifacts(); // final reconciling sync before powering down
  enqueueAction("stopVm", {});
  setMeta("orchestrator_autostop", token);
  setHealth("orchestrator", "ok", { message: `auto-stopping VM after ${status}`, token });
  console.log(`[dashboard-worker] orchestrator ${status}; enqueued stopVm`);
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

let stopping = false;
process.on("SIGINT", () => {
  stopping = true;
});
process.on("SIGTERM", () => {
  stopping = true;
});

async function probeVm(): Promise<string | null> {
  const config = getConfig();
  if (!config.projectId || !config.zone || !config.vmName) {
    setHealth("vm", "unknown", { message: "missing project/zone/vm config" });
    return null;
  }
  const result = await runCommand({
    command: "gcloud",
    args: [
      "compute",
      "instances",
      "describe",
      config.vmName,
      "--project",
      config.projectId,
      "--zone",
      config.zone,
      "--format=value(status)"
    ],
    timeoutMs: 15000
  });
  const status = result.stdout.trim();
  const state = result.exitCode !== 0 ? "warn" : status === "RUNNING" ? "ok" : "idle";
  setHealth("vm", state, {
    status,
    stderr: result.stderr.trim()
  });
  return result.exitCode === 0 ? status : null;
}

function markRemoteIdle(vmStatus: string | null): void {
  const config = getConfig();
  const message = vmStatus ? `VM is ${vmStatus}` : "VM is not running";
  setHealth("ssh", "idle", { host: config.sshHost, message });
  setHealth("remote", "idle", { message });
  setHealth("sync", "idle", { message: "Waiting for VM to run before syncing" });
}

async function probeRemote(vmStatus: string | null): Promise<boolean> {
  const config = getConfig();
  if (vmStatus !== "RUNNING") {
    markRemoteIdle(vmStatus);
    return false;
  }
  if (!config.sshHost) {
    setHealth("ssh", "unknown", { message: "missing ssh host" });
    return false;
  }
  const result = await runCommand({
    command: "ssh",
    args: [
      "-o",
      "BatchMode=yes",
      "-o",
      "ConnectTimeout=5",
      config.sshHost,
      `${config.remoteRepoPath}/infra/remote/dashboard_probe.sh`
    ],
    timeoutMs: 10000
  });
  if (result.exitCode !== 0) {
    setHealth("ssh", "warn", { stderr: result.stderr.trim(), stdout: result.stdout.trim() });
    return false;
  }
  try {
    setHealth("remote", "ok", JSON.parse(result.stdout));
  } catch {
    setHealth("remote", "warn", { stdout: result.stdout.trim() });
  }
  setHealth("ssh", "ok", { host: config.sshHost });
  return true;
}

async function syncSmallArtifacts(): Promise<void> {
  const config = getConfig();
  if (!config.sshHost) return;
  const remoteResults = `${config.sshHost}:${config.remoteRepoPath}/results/`;
  const result = await runCommand({
    command: "rsync",
    args: [
      "-az",
      "--prune-empty-dirs",
      "--include",
      "*/",
      "--include",
      "*.json",
      "--include",
      "*.jsonl",
      "--include",
      "*.csv",
      "--include",
      "*.md",
      "--include",
      "*.txt",
      "--include",
      "*.log",
      "--include",
      "*.png",
      "--include",
      "*.pdf",
      "--include",
      "*.svg",
      "--include",
      "*.sh",
      "--include",
      "status",
      "--include",
      "pid",
      "--include",
      "start_utc",
      "--include",
      "end_utc",
      "--include",
      "exit_code",
      "--exclude",
      "checkpoints/**",
      "--exclude",
      "cache/**",
      "--exclude",
      "*.zarr/**",
      "--exclude",
      "*",
      remoteResults,
      `${config.repoRoot}/results/`
    ],
    timeoutMs: 45000
  });
  setHealth(result.exitCode === 0 ? "sync" : "sync", result.exitCode === 0 ? "ok" : "warn", {
    exitCode: result.exitCode,
    stderr: result.stderr.trim(),
    stdout: result.stdout.trim()
  });
}

async function main(): Promise<void> {
  console.log("[dashboard-worker] starting");
  let vmProbeAt = 0;
  let remoteProbeAt = 0;
  let syncAt = 0;
  let lastVmStatus: string | null = null;
  while (!stopping) {
    const now = Date.now();
    try {
      setHealth("worker", "ok", { pid: process.pid });
      await executePendingActions(1);
      refreshIndex("worker");
      if (now >= vmProbeAt) {
        lastVmStatus = await probeVm();
        vmProbeAt = now + 15000;
      }
      if (now >= remoteProbeAt) {
        const remoteOk = await probeRemote(lastVmStatus);
        remoteProbeAt = now + (remoteOk ? 5000 : 15000);
        if (remoteOk && now >= syncAt) {
          await syncSmallArtifacts();
          syncAt = now + 10000;
          refreshIndex("sync");
        }
      }
      // Checked every loop (not gated behind the sync cadence) so it fires promptly after the laptop
      // resumes from sleep. Self-guards on VM status + a one-shot meta token.
      await maybeAutoStopOnComplete(lastVmStatus);
    } catch (error) {
      setHealth("worker", "warn", { error: error instanceof Error ? error.message : String(error) });
    }
    await sleep(2000);
  }
  setHealth("worker", "unknown", { stopped: true });
  console.log("[dashboard-worker] stopped");
}

void main();
