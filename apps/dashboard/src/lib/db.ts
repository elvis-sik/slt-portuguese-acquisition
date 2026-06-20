import { DatabaseSync } from "node:sqlite";
import { ensureDir, nowIso } from "./files";
import { getConfig } from "./paths";

let db: DatabaseSync | null = null;

export function getDb(): DatabaseSync {
  if (db) return db;
  const config = getConfig();
  ensureDir(config.dataDir);
  db = new DatabaseSync(config.dbPath, { timeout: 5000 });
  db.exec(`
    PRAGMA busy_timeout = 5000;
    PRAGMA journal_mode = WAL;
    CREATE TABLE IF NOT EXISTS meta (
      key TEXT PRIMARY KEY,
      value TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS health (
      key TEXT PRIMARY KEY,
      state TEXT NOT NULL,
      value_json TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS runs (
      id TEXT PRIMARY KEY,
      phase TEXT NOT NULL,
      status TEXT NOT NULL,
      condition TEXT NOT NULL,
      model TEXT NOT NULL,
      seed TEXT NOT NULL,
      git_commit TEXT NOT NULL,
      config_path TEXT NOT NULL,
      start_utc TEXT NOT NULL,
      end_utc TEXT NOT NULL,
      gpu_hours REAL,
      estimated_cost_usd REAL,
      output_dir TEXT NOT NULL,
      notes TEXT NOT NULL,
      parent_run_id TEXT,
      parent_checkpoint_id TEXT,
      updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS jobs (
      id TEXT PRIMARY KEY,
      status TEXT NOT NULL,
      pid TEXT NOT NULL,
      start_utc TEXT NOT NULL,
      end_utc TEXT NOT NULL,
      exit_code TEXT NOT NULL,
      process_alive INTEGER NOT NULL,
      command TEXT NOT NULL,
      log_path TEXT NOT NULL,
      output_dir TEXT NOT NULL,
      last_log_line TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS metrics (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      run_id TEXT NOT NULL,
      name TEXT NOT NULL,
      step REAL,
      value REAL NOT NULL,
      timestamp_utc TEXT,
      source_path TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS artifacts (
      path TEXT PRIMARY KEY,
      kind TEXT NOT NULL,
      size_bytes INTEGER NOT NULL,
      mtime_ms REAL NOT NULL,
      run_id TEXT,
      phase TEXT
    );
    CREATE TABLE IF NOT EXISTS actions (
      id TEXT PRIMARY KEY,
      type TEXT NOT NULL,
      status TEXT NOT NULL,
      created_at TEXT NOT NULL,
      started_at TEXT,
      ended_at TEXT,
      args_json TEXT NOT NULL,
      stdout TEXT NOT NULL DEFAULT '',
      stderr TEXT NOT NULL DEFAULT '',
      exit_code INTEGER,
      message TEXT NOT NULL DEFAULT ''
    );
  `);
  return db;
}

export function setMeta(key: string, value: unknown): void {
  getDb()
    .prepare(
      "INSERT INTO meta (key, value, updated_at) VALUES (?, ?, ?) " +
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at"
    )
    .run(key, JSON.stringify(value), nowIso());
}

export function setHealth(key: string, state: string, value: unknown): void {
  getDb()
    .prepare(
      "INSERT INTO health (key, state, value_json, updated_at) VALUES (?, ?, ?, ?) " +
        "ON CONFLICT(key) DO UPDATE SET state=excluded.state, value_json=excluded.value_json, updated_at=excluded.updated_at"
    )
    .run(key, state, JSON.stringify(value), nowIso());
}

export function resetIndexedTables(): void {
  getDb().exec("DELETE FROM runs; DELETE FROM jobs; DELETE FROM metrics; DELETE FROM artifacts;");
}
