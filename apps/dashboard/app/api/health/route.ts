import { getSnapshot } from "@/lib/snapshot";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const snapshot = getSnapshot({ refresh: false });
  return Response.json({
    generatedAt: snapshot.generatedAt,
    summary: snapshot.summary,
    health: snapshot.health
  });
}
