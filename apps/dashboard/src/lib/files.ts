import fs from "node:fs";
import path from "node:path";
import { toRepoRelative } from "./paths";

export function nowIso(): string {
  return new Date().toISOString();
}

export function safeReadText(filePath: string): string {
  try {
    return fs.readFileSync(filePath, "utf8");
  } catch {
    return "";
  }
}

export function safeReadJson(filePath: string): Record<string, unknown> | null {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8")) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export function ensureDir(dirPath: string): void {
  fs.mkdirSync(dirPath, { recursive: true });
}

export function walkFiles(root: string): string[] {
  if (!fs.existsSync(root)) return [];
  const out: string[] = [];
  const stack = [root];
  while (stack.length) {
    const current = stack.pop()!;
    const entries = fs.readdirSync(current, { withFileTypes: true });
    for (const entry of entries) {
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) stack.push(full);
      else if (entry.isFile()) out.push(full);
    }
  }
  return out;
}

export function fileKind(filePath: string): string {
  if (filePath.includes(".zarr/")) return "zarr";
  const ext = path.extname(filePath).toLowerCase();
  if ([".json", ".jsonl", ".csv", ".md", ".txt", ".log", ".yaml", ".yml"].includes(ext)) {
    return ext.slice(1);
  }
  return ext ? ext.slice(1) : "file";
}

export function logTail(filePath: string, lines = 80): string {
  const text = safeReadText(filePath);
  if (!text) return "";
  return text.split(/\r?\n/).slice(-lines).join("\n");
}

export function lastNonEmptyLine(filePath: string): string {
  const lines = safeReadText(filePath)
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  return lines.at(-1) ?? "";
}

export function statOrNull(filePath: string): fs.Stats | null {
  try {
    return fs.statSync(filePath);
  } catch {
    return null;
  }
}

export function artifactRunHint(filePath: string): { runId: string | null; phase: string | null } {
  const rel = toRepoRelative(filePath);
  const parts = rel.split("/");
  if (parts[0] !== "results") return { runId: null, phase: null };
  if (parts[1] === "_jobs") return { runId: parts[2] ?? null, phase: "_jobs" };
  if (!parts[1] || parts[1].includes(".")) return { runId: null, phase: null };
  if (parts.length === 3 && parts[2]?.includes(".")) return { runId: parts[1], phase: parts[1] };
  return { runId: parts[2] ?? parts[1] ?? null, phase: parts[1] ?? null };
}
