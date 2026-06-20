import fs from "node:fs";
import path from "node:path";
import { repoPath } from "@/lib/paths";
import { safeReadJson } from "@/lib/files";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Lists the orchestrator's Codex agent runs (planner-* and exec-*) from results/_codex.
// The event streams themselves are fetched lazily, per run, via /api/artifacts — so this
// endpoint stays cheap and the heavy logs only load when the operator opens a run.
export async function GET() {
  const root = repoPath("results", "_codex");
  if (!fs.existsSync(root)) return Response.json({ runs: [] });
  const runs: Array<Record<string, unknown>> = [];
  for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const dir = path.join(root, entry.name);
    const eventsPath = path.join(dir, "events.jsonl");
    let mtimeMs = 0;
    let sizeBytes = 0;
    let hasEvents = false;
    try {
      const stat = fs.statSync(eventsPath);
      mtimeMs = stat.mtimeMs;
      sizeBytes = stat.size;
      hasEvents = true;
    } catch {
      // No events yet (run may still be starting); still list the directory.
    }
    const decision = safeReadJson(path.join(dir, "final_decision.json")) as Record<string, unknown> | null;
    runs.push({
      run: entry.name,
      // dir names are "<launch-id>-planner-NNN" or "<launch-id>-exec-<stage>-NNN" (older runs omit the prefix)
      kind: entry.name.includes("planner") ? "planner" : "executor",
      mtimeMs,
      sizeBytes,
      hasEvents,
      eventsPath: `results/_codex/${entry.name}/events.jsonl`,
      decision: decision
        ? {
            status: decision.status ?? decision.terminal_decision ?? null,
            gateDecision: decision.gate_decision ?? null,
            summary: String(decision.summary ?? decision.rationale ?? "").slice(0, 240)
          }
        : null
    });
  }
  runs.sort((a, b) => Number(b.mtimeMs) - Number(a.mtimeMs));
  return Response.json({ runs });
}
