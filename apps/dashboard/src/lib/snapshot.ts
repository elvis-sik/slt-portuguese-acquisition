import { getDb } from "./db";
import { logTail, safeReadJson, safeReadText } from "./files";
import { getConfig, repoPath } from "./paths";
import { csvObjects } from "./parse";
import { refreshIndex } from "./indexer";
import type {
  ActionRecord,
  ArtifactRecord,
  HealthRecord,
  JobRecord,
  MetricPoint,
  RunRecord,
  Snapshot
} from "./types";

type SqlInput = null | number | bigint | string | NodeJS.ArrayBufferView;

function parseJson<T>(value: unknown, fallback: T): T {
  if (typeof value !== "string") return fallback;
  try {
    return JSON.parse(value) as T;
  } catch {
    return fallback;
  }
}

function all<T>(sql: string, ...params: SqlInput[]): T[] {
  return getDb().prepare(sql).all(...params) as T[];
}

function latestMetricsForRun(runId: string): Record<string, number> {
  const rows = all<{ name: string; value: number }>(
    `SELECT m.name, m.value
     FROM metrics m
     JOIN (
       SELECT name, max(id) as max_id FROM metrics WHERE run_id = ? GROUP BY name
     ) latest ON latest.max_id = m.id
     ORDER BY m.name`,
    runId
  );
  return Object.fromEntries(rows.map((row) => [row.name, Number(row.value)]));
}

export function getSnapshot(options: { refresh?: boolean } = {}): Snapshot {
  if (options.refresh !== false) refreshIndex("snapshot");
  const config = getConfig();
  const rawRuns = all<Record<string, unknown>>("SELECT * FROM runs ORDER BY start_utc DESC, id DESC");
  const runs: RunRecord[] = rawRuns.map((row) => {
    const id = String(row.id);
    const checkpointCount = all<{ count: number }>(
      "SELECT count(*) as count FROM artifacts WHERE run_id = ? AND path LIKE '%checkpoint%'",
      id
    )[0]?.count ?? 0;
    return {
      id,
      phase: String(row.phase ?? ""),
      status: String(row.status ?? ""),
      condition: String(row.condition ?? ""),
      model: String(row.model ?? ""),
      seed: String(row.seed ?? ""),
      gitCommit: String(row.git_commit ?? ""),
      configPath: String(row.config_path ?? ""),
      startUtc: String(row.start_utc ?? ""),
      endUtc: String(row.end_utc ?? ""),
      gpuHours: row.gpu_hours === null ? null : Number(row.gpu_hours),
      estimatedCostUsd: row.estimated_cost_usd === null ? null : Number(row.estimated_cost_usd),
      outputDir: String(row.output_dir ?? ""),
      notes: String(row.notes ?? ""),
      parentRunId: row.parent_run_id ? String(row.parent_run_id) : null,
      parentCheckpointId: row.parent_checkpoint_id ? String(row.parent_checkpoint_id) : null,
      checkpointCount: Number(checkpointCount),
      latestMetrics: latestMetricsForRun(id),
      lastHeartbeat: null
    };
  });
  const jobs = all<Record<string, unknown>>("SELECT * FROM jobs ORDER BY start_utc DESC, id DESC").map(
    (row): JobRecord => ({
      id: String(row.id),
      status: String(row.status),
      pid: String(row.pid ?? ""),
      startUtc: String(row.start_utc ?? ""),
      endUtc: String(row.end_utc ?? ""),
      exitCode: String(row.exit_code ?? ""),
      processAlive: Boolean(row.process_alive),
      command: String(row.command ?? ""),
      logPath: String(row.log_path ?? ""),
      outputDir: String(row.output_dir ?? ""),
      lastLogLine: String(row.last_log_line ?? ""),
      updatedAt: String(row.updated_at ?? "")
    })
  );
  const metrics = all<Record<string, unknown>>(
    "SELECT run_id, name, step, value, timestamp_utc, source_path FROM metrics ORDER BY id DESC LIMIT 800"
  ).map(
    (row): MetricPoint => ({
      runId: String(row.run_id),
      name: String(row.name),
      step: row.step === null ? null : Number(row.step),
      value: Number(row.value),
      timestampUtc: row.timestamp_utc ? String(row.timestamp_utc) : null,
      sourcePath: String(row.source_path)
    })
  );
  const artifacts = all<Record<string, unknown>>(
    "SELECT * FROM artifacts ORDER BY mtime_ms DESC LIMIT 600"
  ).map(
    (row): ArtifactRecord => ({
      path: String(row.path),
      kind: String(row.kind),
      sizeBytes: Number(row.size_bytes),
      mtimeMs: Number(row.mtime_ms),
      runId: row.run_id ? String(row.run_id) : null,
      phase: row.phase ? String(row.phase) : null
    })
  );
  const actions = all<Record<string, unknown>>("SELECT * FROM actions ORDER BY created_at DESC LIMIT 100").map(
    (row): ActionRecord => ({
      id: String(row.id),
      type: String(row.type),
      status: String(row.status) as ActionRecord["status"],
      createdAt: String(row.created_at),
      startedAt: row.started_at ? String(row.started_at) : null,
      endedAt: row.ended_at ? String(row.ended_at) : null,
      args: parseJson<Record<string, unknown>>(row.args_json, {}),
      stdout: String(row.stdout ?? ""),
      stderr: String(row.stderr ?? ""),
      exitCode: row.exit_code === null ? null : Number(row.exit_code),
      message: String(row.message ?? "")
    })
  );
  const health = all<Record<string, unknown>>("SELECT * FROM health ORDER BY key").map(
    (row): HealthRecord => ({
      key: String(row.key),
      state: String(row.state) as HealthRecord["state"],
      updatedAt: String(row.updated_at),
      data: parseJson<Record<string, unknown>>(row.value_json, {})
    })
  );
  const currentStatus = safeReadJson(repoPath("state", "current_status.json"));
  const estimate = safeReadJson(repoPath("results", "00_infrastructure_gate", "project_estimate.json"));
  const projectedMedianHours =
    typeof estimate?.charged_hours === "object" && estimate.charged_hours !== null
      ? Number((estimate.charged_hours as Record<string, unknown>).median)
      : null;
  const estimatedCostUsd =
    typeof currentStatus?.estimated_cost_usd === "number" ? currentStatus.estimated_cost_usd : null;
  const registryRows = csvObjects(safeReadText(repoPath("state", "experiment_registry.csv"))).length;

  return {
    generatedAt: new Date().toISOString(),
    config,
    summary: {
      runCount: runs.length,
      jobCount: jobs.length,
      runningJobCount: jobs.filter((job) => job.status === "running").length,
      actionCount: actions.length,
      pendingActionCount: actions.filter((action) => action.status === "pending").length,
      estimatedCostUsd,
      projectedMedianHours: Number.isFinite(projectedMedianHours) ? projectedMedianHours : null
    },
    health,
    runs,
    jobs,
    metrics,
    artifacts,
    actions,
    currentStatus,
    decisionLogTail: logTail(repoPath("state", "decision_log.md"), 80),
    registryRows
  };
}
