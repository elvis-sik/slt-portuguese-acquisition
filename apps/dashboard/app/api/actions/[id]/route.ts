import { getDb } from "@/lib/db";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(_request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  const row = getDb().prepare("SELECT * FROM actions WHERE id = ?").get(id);
  if (!row) return Response.json({ error: "not found" }, { status: 404 });
  return Response.json(row);
}
