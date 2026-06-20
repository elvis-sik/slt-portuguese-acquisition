import fs from "node:fs";
import path from "node:path";
import { getDb, resetIndexedTables, setMeta } from "./db";
import {
  artifactRunHint,
  fileKind,
  lastNonEmptyLine,
  safeReadJson,
  safeReadText,
  statOrNull,
  walkFiles
} from "./files";
import { repoPath, toRepoRelative } from "./paths";
import { asNumber, csvObjects, numericEntries } from "./parse";

type ArtifactHint = { runId: string | null; phase: string | null };
type OutputDirHint = { runId: string; phase: string; outputDir: string };

function upsertRun(row: Record<string, string>): void {
  const db = getDb();
  db.prepare(
    `INSERT INTO runs (
      id, phase, status, condition, model, seed, git_commit, config_path, start_utc, end_utc,
      gpu_hours, estimated_cost_usd, output_dir, notes, parent_run_id, parent_checkpoint_id, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET
      phase=excluded.phase, status=excluded.status, condition=excluded.condition, model=excluded.model,
      seed=excluded.seed, git_commit=excluded.git_commit, config_path=excluded.config_path,
      start_utc=excluded.start_utc, end_utc=excluded.end_utc, gpu_hours=excluded.gpu_hours,
      estimated_cost_usd=excluded.estimated_cost_usd, output_dir=excluded.output_dir, notes=excluded.notes,
      parent_run_id=excluded.parent_run_id, parent_checkpoint_id=excluded.parent_checkpoint_id,
      updated_at=excluded.updated_at`
  ).run(
    row.run_id || "unknown",
    row.phase || "",
    row.status || "",
    row.condition || "",
    row.model || "",
    row.seed || "",
    row.git_commit || "",
    row.config_path || "",
    row.start_utc || "",
    row.end_utc || "",
    asNumber(row.gpu_hours),
    asNumber(row.estimated_cost_usd),
    row.output_dir || "",
    row.notes || "",
    row.parent_run_id || null,
    row.parent_checkpoint_id || null,
    new Date().toISOString()
  );
}

function indexRuns(): number {
  const registry = repoPath("state", "experiment_registry.csv");
  const rows = csvObjects(safeReadText(registry));
  for (const row of rows) upsertRun(row);
  return rows.length;
}

function indexJobs(): number {
  const root = repoPath("results", "_jobs");
  if (!fs.existsSync(root)) return 0;
  let count = 0;
  const db = getDb();
  for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const dir = path.join(root, entry.name);
    const logPath = path.join(dir, "stdout_stderr.log");
    db.prepare(
      `INSERT INTO jobs (
        id, status, pid, start_utc, end_utc, exit_code, process_alive, command,
        log_path, output_dir, last_log_line, updated_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(id) DO UPDATE SET
        status=excluded.status, pid=excluded.pid, start_utc=excluded.start_utc, end_utc=excluded.end_utc,
        exit_code=excluded.exit_code, process_alive=excluded.process_alive, command=excluded.command,
        log_path=excluded.log_path, output_dir=excluded.output_dir, last_log_line=excluded.last_log_line,
        updated_at=excluded.updated_at`
    ).run(
      entry.name,
      safeReadText(path.join(dir, "status")).trim() || "unknown",
      safeReadText(path.join(dir, "pid")).trim(),
      safeReadText(path.join(dir, "start_utc")).trim(),
      safeReadText(path.join(dir, "end_utc")).trim(),
      safeReadText(path.join(dir, "exit_code")).trim(),
      0,
      safeReadText(path.join(dir, "command.sh")).trim(),
      toRepoRelative(logPath),
      toRepoRelative(dir),
      lastNonEmptyLine(logPath),
      new Date().toISOString()
    );
    count += 1;
  }
  return count;
}

function addMetric(runId: string, name: string, step: number | null, value: number, sourcePath: string, timestamp: string | null): void {
  getDb()
    .prepare("INSERT INTO metrics (run_id, name, step, value, timestamp_utc, source_path) VALUES (?, ?, ?, ?, ?, ?)")
    .run(runId, name, step, value, timestamp, toRepoRelative(sourcePath));
}

function outputDirHints(): OutputDirHint[] {
  return (
    getDb()
      .prepare(
        `SELECT id, phase, output_dir FROM runs
         WHERE output_dir != ''
         ORDER BY length(output_dir) DESC,
           CASE WHEN id LIKE '%consolidated%' THEN 0 ELSE 1 END,
           start_utc ASC`
      )
      .all() as Array<Record<string, unknown>>
  )
    .map((row) => ({
      runId: String(row.id),
      phase: String(row.phase ?? ""),
      outputDir: String(row.output_dir ?? "").replace(/\/+$/, "")
    }))
    .filter((row) => row.outputDir.startsWith("results/"));
}

function hintForArtifact(filePath: string, outputHints: OutputDirHint[]): ArtifactHint {
  const rel = toRepoRelative(filePath);
  for (const hint of outputHints) {
    if (rel === hint.outputDir || rel.startsWith(`${hint.outputDir}/`)) {
      return { runId: hint.runId, phase: hint.phase };
    }
  }
  return artifactRunHint(filePath);
}

function indexJsonMetrics(filePath: string, hint: ArtifactHint): void {
  const data = safeReadJson(filePath);
  if (!data) return;
  const rel = toRepoRelative(filePath);
  const { runId } = hint;
  const id = runId ?? path.basename(filePath, ".json");
  const timestamp = typeof data.timestamp_utc === "string" ? data.timestamp_utc : null;
  const sequence = asNumber(data.sequence_length);
  for (const [name, value] of numericEntries(data)) {
    addMetric(id, name, sequence, value, filePath, timestamp);
  }
  if (rel.endsWith("project_estimate.json")) {
    const charged = data.charged_hours as Record<string, unknown> | undefined;
    if (charged) {
      for (const [name, value] of numericEntries(charged)) {
        addMetric(id, `charged_hours_${name}`, null, value, filePath, timestamp);
      }
    }
  }
  if (rel.endsWith("sampler_smoke.json")) {
    const result = data.result as Record<string, unknown> | undefined;
    const vars = result?.data_vars as Record<string, Record<string, unknown>> | undefined;
    if (vars) {
      for (const key of ["llc_mean", "llc_std", "init_loss"]) {
        const value = asNumber(vars[key]?.data);
        if (value !== null) addMetric(id, key, null, value, filePath, timestamp);
      }
    }
  }
}

function indexJsonlMetrics(filePath: string, hint: ArtifactHint): void {
  const { runId } = hint;
  const id = runId ?? path.basename(path.dirname(filePath));
  for (const line of safeReadText(filePath).split(/\r?\n/)) {
    if (!line.trim()) continue;
    try {
      const data = JSON.parse(line) as Record<string, unknown>;
      const step = asNumber(data.step ?? data.global_step ?? data.tokens);
      const timestamp = typeof data.timestamp_utc === "string" ? data.timestamp_utc : null;
      for (const [name, value] of numericEntries(data)) {
        if (!["step", "global_step", "tokens"].includes(name)) addMetric(id, name, step, value, filePath, timestamp);
      }
    } catch {
      // Leave malformed lines in the artifact log; do not hide the file.
    }
  }
}

function indexArtifactsAndMetrics(): number {
  const root = repoPath("results");
  if (!fs.existsSync(root)) return 0;
  const db = getDb();
  let count = 0;
  const outputHints = outputDirHints();
  for (const file of walkFiles(root)) {
    const rel = toRepoRelative(file);
    const stat = statOrNull(file);
    if (!stat) continue;
    const hint = hintForArtifact(file, outputHints);
    db.prepare(
      `INSERT INTO artifacts (path, kind, size_bytes, mtime_ms, run_id, phase)
       VALUES (?, ?, ?, ?, ?, ?)
       ON CONFLICT(path) DO UPDATE SET kind=excluded.kind, size_bytes=excluded.size_bytes,
       mtime_ms=excluded.mtime_ms, run_id=excluded.run_id, phase=excluded.phase`
    ).run(rel, fileKind(file), stat.size, stat.mtimeMs, hint.runId, hint.phase);
    if (rel.endsWith(".json")) indexJsonMetrics(file, hint);
    if (rel.endsWith(".jsonl")) indexJsonlMetrics(file, hint);
    count += 1;
  }
  return count;
}

export function refreshIndex(reason = "manual"): { runs: number; jobs: number; artifacts: number } {
  resetIndexedTables();
  const runs = indexRuns();
  const jobs = indexJobs();
  const artifacts = indexArtifactsAndMetrics();
  setMeta("last_index", { reason, runs, jobs, artifacts });
  return { runs, jobs, artifacts };
}
