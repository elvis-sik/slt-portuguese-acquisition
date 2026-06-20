import { actionDefinitions, enqueueAction } from "@/lib/actions";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  return Response.json({ actions: actionDefinitions });
}

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as { type?: string; args?: unknown };
    if (!body.type) return Response.json({ error: "type is required" }, { status: 400 });
    const id = enqueueAction(body.type, body.args ?? {});
    return Response.json({ id }, { status: 202 });
  } catch (error) {
    return Response.json({ error: error instanceof Error ? error.message : String(error) }, { status: 400 });
  }
}
