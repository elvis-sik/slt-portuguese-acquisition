import { getSnapshot } from "@/lib/snapshot";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const encoder = new TextEncoder();
  let closed = false;
  const stream = new ReadableStream({
    start(controller) {
      const send = () => {
        if (closed) return;
        try {
          const payload = JSON.stringify(getSnapshot({ refresh: false }));
          controller.enqueue(encoder.encode(`event: snapshot\ndata: ${payload}\n\n`));
        } catch (error) {
          const message = error instanceof Error ? error.message : String(error);
          controller.enqueue(encoder.encode(`event: error\ndata: ${JSON.stringify({ message })}\n\n`));
        }
      };
      send();
      const interval = setInterval(send, 2500);
      return () => clearInterval(interval);
    },
    cancel() {
      closed = true;
    }
  });
  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive"
    }
  });
}
