import fs from "node:fs";
import path from "node:path";
import { getConfig, toRepoRelative } from "@/lib/paths";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function resolveArtifact(parts: string[]): string | null {
  const safeParts = parts[0] === "results" ? parts.slice(1) : parts;
  if (safeParts.some((part) => part === ".." || part.includes("/") || part.includes("\\"))) return null;
  const resultsRoot = path.join(/* turbopackIgnore: true */ getConfig().repoRoot, "results");
  const target = path.normalize(path.join(resultsRoot, ...safeParts));
  const relative = path.relative(resultsRoot, target);
  if (relative.startsWith("..") || path.isAbsolute(relative)) return null;
  return target;
}

export async function GET(request: Request, context: { params: Promise<{ path: string[] }> }) {
  const { path: parts } = await context.params;
  const target = resolveArtifact(parts);
  if (!target || !fs.existsSync(target)) return Response.json({ error: "not found" }, { status: 404 });
  const stat = fs.statSync(target);
  const url = new URL(request.url);
  if (stat.isDirectory() || url.searchParams.get("metadata") === "1") {
    return Response.json({
      path: toRepoRelative(target),
      sizeBytes: stat.size,
      mtimeMs: stat.mtimeMs,
      isDirectory: stat.isDirectory()
    });
  }
  return new Response(fs.readFileSync(target), {
    headers: {
      "Content-Type": "application/octet-stream",
      "Content-Disposition": `attachment; filename="${path.basename(target)}"`
    }
  });
}
