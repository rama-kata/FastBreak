import { apiHeaders, apiUrl } from "@/lib/api";

// Thinking answers have taken up to about 160 s; leave room for that.
export const maxDuration = 300;

function problem(status: number, detail: string) {
  return Response.json({ detail }, { status });
}

/** Passes a question to the FastBreak API and streams its events back, adding the API key. */
export async function POST(request: Request) {
  const body = await request.json().catch(() => null);
  const question = typeof body?.question === "string" ? body.question.trim() : "";
  if (!question) return problem(400, "Type a question first.");

  // Vercel sets these; the API limits questions per visitor by this address.
  const client =
    request.headers.get("x-real-ip") ?? request.headers.get("x-forwarded-for")?.split(",")[0].trim() ?? "";

  let upstream: Response;
  try {
    upstream = await fetch(apiUrl("/api/ask"), {
      method: "POST",
      headers: { ...apiHeaders(), "Content-Type": "application/json", "X-FastBreak-Client": client },
      body: JSON.stringify({ question }),
      signal: request.signal,
    });
  } catch {
    return problem(502, "FastBreak's data server is offline right now. Try again later.");
  }
  if (!upstream.ok || !upstream.body) {
    const detail = await upstream.json().then((j) => j.detail).catch(() => null);
    if (upstream.status === 422) return problem(422, "Questions can be up to 300 characters.");
    return problem(upstream.status, typeof detail === "string" ? detail : "Something went wrong.");
  }
  return new Response(upstream.body, {
    headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache, no-transform" },
  });
}
