import fs from "node:fs";
import path from "node:path";
import { getDb } from "./db";
import { ensureDir, nowIso } from "./files";
import { getConfig } from "./paths";
import { actionDefinitions, validateAction, type ActionType } from "./action-registry";
import { localScript, runCommand, type CommandSpec } from "./commands";

export { actionDefinitions };

function id(prefix = "act"): string {
  return `${prefix}_${new Date().toISOString().replace(/[-:.TZ]/g, "")}_${Math.random()
    .toString(36)
    .slice(2, 8)}`;
}

function dbText(value: unknown, fallback = ""): string {
  if (typeof value === "string") return value;
  if (value === null || value === undefined) return fallback;
  return String(value);
}

function dbNullableText(value: unknown): string | null {
  if (value === null || value === undefined || value === "") return null;
  return String(value);
}

function dbNullableNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "bigint") return Number(value);
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

export function enqueueAction(type: string, rawArgs: unknown): string {
  const { type: validType, args } = validateAction(type, rawArgs);
  const actionId = id(validType);
  getDb()
    .prepare(
      "INSERT INTO actions (id, type, status, created_at, args_json, stdout, stderr, message) VALUES (?, ?, 'pending', ?, ?, '', '', '')"
    )
    .run(actionId, validType, nowIso(), JSON.stringify(args));
  return actionId;
}

function updateAction(
  actionId: string,
  fields: Partial<{
    status: string;
    started_at: string | null;
    ended_at: string | null;
    stdout: string;
    stderr: string;
    exit_code: number | null;
    message: string;
  }>
): void {
  const current = getDb().prepare("SELECT * FROM actions WHERE id = ?").get(actionId) as Record<string, unknown> | undefined;
  if (!current) return;
  getDb()
    .prepare(
      `UPDATE actions SET status=?, started_at=?, ended_at=?, stdout=?, stderr=?, exit_code=?, message=? WHERE id=?`
    )
    .run(
      fields.status ?? dbText(current.status),
      fields.started_at === undefined ? dbNullableText(current.started_at) : fields.started_at,
      fields.ended_at === undefined ? dbNullableText(current.ended_at) : fields.ended_at,
      fields.stdout ?? dbText(current.stdout),
      fields.stderr ?? dbText(current.stderr),
      fields.exit_code === undefined ? dbNullableNumber(current.exit_code) : fields.exit_code,
      fields.message ?? dbText(current.message),
      actionId
    );
}

function buildSyncSpec(direction: "pull" | "push-control"): CommandSpec {
  const config = getConfig();
  if (!config.sshHost) throw new Error("DASHBOARD_SSH_HOST or VM_NAME/ZONE/PROJECT_ID is required");
  const remoteResults = `${config.sshHost}:${config.remoteRepoPath}/results/`;
  const localResults = path.join(config.repoRoot, "results") + "/";
  const includes = [
    "*/",
    "*.json",
    "*.jsonl",
    "*.csv",
    "*.md",
    "*.txt",
    "*.log",
    "*.png",
    "*.pdf",
    "*.svg",
    "*.sh",
    "status",
    "pid",
    "start_utc",
    "end_utc",
    "exit_code"
  ];
  if (direction === "push-control") {
    return {
      command: "rsync",
      args: ["-az", path.join(config.repoRoot, "results", "_control") + "/", `${remoteResults}_control/`],
      timeoutMs: 30000
    };
  }
  return {
    command: "rsync",
    args: [
      "-az",
      "--prune-empty-dirs",
      ...includes.flatMap((pattern) => ["--include", pattern]),
      "--exclude",
      "checkpoints/**",
      "--exclude",
      "cache/**",
      "--exclude",
      "*.zarr/**",
      "--exclude",
      "*",
      remoteResults,
      localResults
    ],
    timeoutMs: 45000
  };
}

function buildSpawnAction(type: ActionType, args: Record<string, unknown>): CommandSpec | null {
  const config = getConfig();
  const env = { ...process.env, ENV_FILE: config.envFile };
  if (type === "startVm") {
    return { command: localScript(config, "infra/gcp/start_vm.sh"), args: [], cwd: config.repoRoot, env, timeoutMs: 120000 };
  }
  if (type === "stopVm") {
    return { command: localScript(config, "infra/gcp/stop_vm.sh"), args: [], cwd: config.repoRoot, env, timeoutMs: 120000 };
  }
  if (type === "syncNow") {
    return buildSyncSpec((args.direction as "pull" | "push-control") ?? "pull");
  }
  if (!config.sshHost) throw new Error("DASHBOARD_SSH_HOST or VM_NAME/ZONE/PROJECT_ID is required");
  if (type === "startBoundedJob") {
    const jobArgs = [
      config.sshHost,
      `${config.remoteRepoPath}/infra/remote/dashboard_action.sh`,
      "start-bounded-job",
      "--template",
      String(args.templateId),
      "--name",
      String(args.jobName),
      "--max-hours",
      String(args.maxHours)
    ];
    for (const [flag, value] of [
      ["--max-epochs", args.maxEpochs],
      ["--max-steps", args.maxSteps],
      ["--max-tokens", args.maxTokens]
    ] as const) {
      if (value !== undefined && value !== null && value !== "") jobArgs.push(flag, String(value));
    }
    return {
      command: "ssh",
      args: jobArgs,
      timeoutMs: 30000
    };
  }
  if (type === "stopJob") {
    return {
      command: "ssh",
      args: [config.sshHost, `${config.remoteRepoPath}/infra/remote/stop_job.sh`, String(args.jobName)],
      timeoutMs: 30000
    };
  }
  if (type === "startOrchestrator") {
    const orchArgs = [
      config.sshHost,
      `${config.remoteRepoPath}/infra/remote/dashboard_action.sh`,
      "start-orchestrator",
      "--deadline-hours",
      String(args.deadlineHours ?? 8),
      "--soft",
      String(args.soft ?? 35),
      "--hard",
      String(args.hard ?? 50)
    ];
    if (args.autoStop === false) orchArgs.push("--no-auto-stop");
    orchArgs.push(
      "--planner-model", config.codexPlannerModel,
      "--planner-effort", config.codexPlannerEffort,
      "--exec-model", config.codexExecModel,
      "--exec-effort", config.codexExecEffort
    );
    return { command: "ssh", args: orchArgs, timeoutMs: 30000 };
  }
  if (type === "stopOrchestrator") {
    const stopArgs = [
      config.sshHost,
      `${config.remoteRepoPath}/infra/remote/dashboard_action.sh`,
      "stop-orchestrator"
    ];
    if (args.kill === true) stopArgs.push("--kill");
    return { command: "ssh", args: stopArgs, timeoutMs: 30000 };
  }
  return null;
}

function writeControlFile(type: ActionType, actionId: string, args: Record<string, unknown>): string {
  const config = getConfig();
  const runId = String(args.runId);
  const dir = path.join(config.repoRoot, "results", "_control", runId, "commands");
  ensureDir(dir);
  const checkpointId = "checkpointId" in args ? String(args.checkpointId) : null;
  const newRunId =
    type === "forkFromCheckpoint"
      ? String(args.newRunId || `${runId}_fork_${new Date().toISOString().replace(/[-:.TZ]/g, "")}`)
      : null;
  const payload = {
    id: actionId,
    type,
    run_id: runId,
    checkpoint_id: checkpointId,
    new_run_id: newRunId,
    note: args.note ?? "",
    created_at: nowIso()
  };
  const fileName = `${payload.created_at.replace(/[-:.TZ]/g, "")}_${type}_${actionId}.json`;
  const filePath = path.join(dir, fileName);
  fs.writeFileSync(filePath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
  return filePath;
}

export async function executePendingActions(limit = 1): Promise<void> {
  const pending = getDb()
    .prepare("SELECT id, type, args_json FROM actions WHERE status = 'pending' ORDER BY created_at ASC LIMIT ?")
    .all(limit) as Array<{ id: string; type: ActionType; args_json: string }>;
  for (const action of pending) {
    updateAction(action.id, { status: "running", started_at: nowIso(), message: "running" });
    try {
      const args = JSON.parse(action.args_json) as Record<string, unknown>;
      if (["checkpointNow", "pauseRun", "resumeRun", "forkFromCheckpoint"].includes(action.type)) {
        const filePath = writeControlFile(action.type, action.id, args);
        let syncMessage = "control queued locally";
        try {
          const result = await runCommand(buildSyncSpec("push-control"));
          syncMessage = result.exitCode === 0 ? "control pushed to remote" : "control queued locally; remote push failed";
          updateAction(action.id, {
            stdout: result.stdout,
            stderr: result.stderr,
            exit_code: result.exitCode,
            message: `${syncMessage}: ${filePath}`
          });
        } catch (error) {
          updateAction(action.id, { stderr: error instanceof Error ? error.message : String(error), message: syncMessage });
        }
        updateAction(action.id, { status: "completed", ended_at: nowIso() });
        continue;
      }
      const spec = buildSpawnAction(action.type, args);
      if (!spec) throw new Error(`No command registered for ${action.type}`);
      const result = await runCommand(spec);
      updateAction(action.id, {
        status: result.exitCode === 0 ? "completed" : "failed",
        ended_at: nowIso(),
        stdout: result.stdout,
        stderr: result.stderr,
        exit_code: result.exitCode,
        message: result.timedOut ? "timed out" : result.command.join(" ")
      });
    } catch (error) {
      updateAction(action.id, {
        status: "failed",
        ended_at: nowIso(),
        stderr: error instanceof Error ? error.stack ?? error.message : String(error),
        exit_code: 1,
        message: "action failed"
      });
    }
  }
}
