import { setHealth } from "@/lib/db";
import { refreshIndex } from "@/lib/indexer";
import { executePendingActions } from "@/lib/actions";
import { getConfig } from "@/lib/paths";
import { runCommand } from "@/lib/commands";

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
  setHealth(result.exitCode === 0 ? "vm" : "vm", result.exitCode === 0 ? "ok" : "warn", {
    status,
    stderr: result.stderr.trim()
  });
  return result.exitCode === 0 ? status : null;
}

async function probeRemote(): Promise<boolean> {
  const config = getConfig();
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
  while (!stopping) {
    const now = Date.now();
    try {
      setHealth("worker", "ok", { pid: process.pid });
      await executePendingActions(1);
      refreshIndex("worker");
      if (now >= vmProbeAt) {
        await probeVm();
        vmProbeAt = now + 15000;
      }
      if (now >= remoteProbeAt) {
        const remoteOk = await probeRemote();
        remoteProbeAt = now + (remoteOk ? 5000 : 15000);
        if (remoteOk && now >= syncAt) {
          await syncSmallArtifacts();
          syncAt = now + 10000;
          refreshIndex("sync");
        }
      }
    } catch (error) {
      setHealth("worker", "warn", { error: error instanceof Error ? error.message : String(error) });
    }
    await sleep(2000);
  }
  setHealth("worker", "unknown", { stopped: true });
  console.log("[dashboard-worker] stopped");
}

void main();
