import fs from "node:fs";
import path from "node:path";
import type { DashboardConfig } from "./types";

let cachedConfig: DashboardConfig | null = null;

export function getRepoRoot(): string {
  return path.resolve(process.env.DASHBOARD_REPO_ROOT ?? path.join(/* turbopackIgnore: true */ process.cwd(), "../.."));
}

export function parseDotEnv(filePath: string): Record<string, string> {
  if (!fs.existsSync(filePath)) return {};
  const result: Record<string, string> = {};
  for (const rawLine of fs.readFileSync(filePath, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const idx = line.indexOf("=");
    if (idx < 1) continue;
    const key = line.slice(0, idx).trim();
    let value = line.slice(idx + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    result[key] = value;
  }
  return result;
}

export function getConfig(): DashboardConfig {
  if (cachedConfig) return cachedConfig;
  const repoRoot = getRepoRoot();
  const dataDir = path.join(repoRoot, ".dashboard");
  const envFile = process.env.DASHBOARD_ENV_FILE ?? path.join(repoRoot, ".env.local");
  const env = { ...parseDotEnv(envFile), ...process.env };
  const projectId = env.PROJECT_ID || null;
  const zone = env.ZONE || null;
  const vmName = env.VM_NAME || null;
  const sshHost =
    env.DASHBOARD_SSH_HOST ||
    (vmName && zone && projectId ? `${vmName}.${zone}.${projectId}` : null);
  const remoteRepoDir = env.REMOTE_REPO_DIR || "slt-portuguese";
  cachedConfig = {
    repoRoot,
    dataDir,
    dbPath: process.env.DASHBOARD_DB_PATH ?? path.join(dataDir, "dashboard.sqlite"),
    envFile,
    projectId,
    zone,
    vmName,
    sshHost,
    remoteRepoPath: env.DASHBOARD_REMOTE_REPO_PATH || `~/${remoteRepoDir}`,
    hourlyRateUsd: Number(env.HOURLY_RATE_USD || "1")
  };
  return cachedConfig;
}

export function repoPath(...segments: string[]): string {
  return path.join(getRepoRoot(), ...segments);
}

export function toRepoRelative(absOrRel: string): string {
  const repoRoot = getRepoRoot();
  const abs = path.isAbsolute(absOrRel) ? absOrRel : path.join(repoRoot, absOrRel);
  return path.relative(repoRoot, abs).split(path.sep).join("/");
}
