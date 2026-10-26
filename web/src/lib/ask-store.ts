// One run per question, kept outside React. Remounts (Strict Mode, back navigation, routes
// kept alive by Activity) subscribe to the same run instead of asking the GPU again.
import type { AskResult } from "./types";

export type RunState = {
  phase: "writing" | "running" | "checking" | "done" | "failed" | "stopped";
  startedAt: number;
  finishedAt: number | null;
  sql: string | null;
  retries: number;
  result: AskResult | null;
  error: string | null;
};

type Run = { state: RunState; listeners: Set<() => void>; controller: AbortController };

const runs = new Map<string, Run>();

function update(run: Run, patch: Partial<RunState>) {
  run.state = { ...run.state, ...patch };
  run.listeners.forEach((l) => l());
}

function finish(run: Run, patch: Partial<RunState>) {
  update(run, { ...patch, finishedAt: Date.now() });
}

function handle(run: Run, event: string, data: Record<string, unknown>) {
  if (event === "sql_written") update(run, { phase: "running", sql: data.sql as string });
  else if (event === "query_failed" && data.retrying)
    update(run, { phase: "writing", retries: run.state.retries + 1 });
  else if (event === "query_done") update(run, { phase: "checking" });
  else if (event === "result") finish(run, { phase: "done", result: data as unknown as AskResult });
  else if (event === "error") finish(run, { phase: "failed", error: data.error as string });
}

async function start(question: string, run: Run) {
  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
      signal: run.controller.signal,
    });
    if (!res.ok || !res.body) {
      const detail = await res.json().then((j) => j.detail).catch(() => null);
      return finish(run, { phase: "failed", error: detail ?? `The server answered ${res.status}.` });
    }
    const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += value;
      let end;
      while ((end = buffer.indexOf("\n\n")) !== -1) {
        const block = buffer.slice(0, end);
        buffer = buffer.slice(end + 2);
        const fields = Object.fromEntries(
          block.split("\n").map((line) => [line.slice(0, line.indexOf(":")), line.slice(line.indexOf(":") + 2)]),
        );
        if (fields.event && fields.data) handle(run, fields.event, JSON.parse(fields.data));
      }
    }
    if (run.state.finishedAt === null)
      finish(run, { phase: "failed", error: "The connection closed before the answer arrived." });
  } catch {
    if (run.state.finishedAt !== null) return;
    if (run.controller.signal.aborted) finish(run, { phase: "stopped" });
    else finish(run, { phase: "failed", error: "Lost the connection to FastBreak." });
  }
}

export const INITIAL: RunState = {
  phase: "writing", startedAt: 0, finishedAt: null, sql: null, retries: 0, result: null,
  error: null,
};

function newRun(question: string, listeners = new Set<() => void>()): Run {
  const run: Run = {
    state: { ...INITIAL, startedAt: Date.now() },
    listeners,
    controller: new AbortController(),
  };
  runs.set(question, run);
  void start(question, run);
  return run;
}

/** Listen to the run for `question`, starting it if there isn't one yet. */
export function subscribe(question: string, listener: () => void) {
  const run = runs.get(question) ?? newRun(question);
  run.listeners.add(listener);
  return () => {
    runs.get(question)?.listeners.delete(listener);
  };
}

export function snapshot(question: string): RunState {
  return runs.get(question)?.state ?? INITIAL;
}

export function stopRun(question: string) {
  runs.get(question)?.controller.abort();
}

/** Ask again: drop the old run and start a new one for the same listeners. */
export function restartRun(question: string) {
  const old = runs.get(question);
  old?.controller.abort();
  const run = newRun(question, old?.listeners);
  run.listeners.forEach((l) => l());
}
