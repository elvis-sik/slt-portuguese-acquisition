import { logTail } from "@/lib/files";
import { repoPath } from "@/lib/paths";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  const url = new URL(request.url);
  const lines = Math.min(500, Math.max(20, Number(url.searchParams.get("lines") || "120")));
  const file = repoPath("results", "_jobs", id, "stdout_stderr.log");
  return Response.json({ id, lines, text: logTail(file, lines) });
}
