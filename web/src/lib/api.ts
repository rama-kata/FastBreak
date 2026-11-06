// Server-side only: these calls carry the API key, which must never reach the browser.
import { connection } from "next/server";
import type { LatestGames, Status } from "./types";

const API_URL = process.env.FASTBREAK_API_URL ?? "http://127.0.0.1:8077";

export function apiHeaders(): HeadersInit {
  const key = process.env.FASTBREAK_API_KEY;
  return key ? { "X-FastBreak-Key": key } : {};
}

export function apiUrl(path: string) {
  return `${API_URL}${path}`;
}

async function getJson<T>(path: string): Promise<T | null> {
  await connection(); // at request time, never baked into the build (outside the try: it must throw)
  try {
    const res = await fetch(apiUrl(path), {
      headers: apiHeaders(),
      signal: AbortSignal.timeout(8000),
    });
    return res.ok ? ((await res.json()) as T) : null;
  } catch {
    return null; // the home PC is off or the tunnel is down: show the page without it
  }
}

export const getStatus = () => getJson<Status>("/api/status");
export const getLatestGames = () => getJson<LatestGames>("/api/games/latest");
