"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import { INITIAL, restartRun, snapshot, stopRun, subscribe, type RunState } from "@/lib/ask-store";
import type { AskResult, Cell } from "@/lib/types";

const label = "m-0 font-display text-sm font-bold uppercase tracking-[0.06em] text-muted";
const button =
  "inline-flex min-h-11 cursor-pointer items-center justify-center rounded-lg px-4 text-sm font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-navy";
const secondary = `${button} border border-line-strong bg-white text-ink hover:bg-chalk`;
const primary = `${button} bg-sun text-ink hover:brightness-95`;

function useRun(question: string): RunState {
  return useSyncExternalStore(
    (listener) => subscribe(question, listener),
    () => snapshot(question),
    () => INITIAL,
  );
}

export function Answer({ question }: { question: string }) {
  const run = useRun(question);
  if (run.phase === "done" && run.result) return <Result result={run.result} question={question} />;
  if (run.phase === "failed" || run.phase === "stopped") return <Failed run={run} question={question} />;
  return <Working run={run} question={question} />;
}

// --- while it works -------------------------------------------------------------------

function Elapsed({ since }: { since: number }) {
  const [now, setNow] = useState(since);
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  const s = Math.max(0, Math.floor((now - since) / 1000));
  return (
    <span className="font-mono text-[15px] text-muted">
      {Math.floor(s / 60)}:{String(s % 60).padStart(2, "0")} elapsed
    </span>
  );
}

type StepState = "done" | "active" | "waiting";

function StepIcon({ state }: { state: StepState }) {
  if (state === "done")
    return (
      <span className="flex size-8 items-center justify-center rounded-full bg-court">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <path d="M3 8.5l3 3 7-7" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
    );
  if (state === "active")
    return (
      <span className="size-8 animate-spin rounded-full border-[3px] border-sun border-t-navy motion-reduce:animate-none" />
    );
  return <span className="size-8 rounded-full border-2 border-line-strong" />;
}

function Step({ state, title, detail, last }: { state: StepState; title: string; detail: string; last?: boolean }) {
  const status = { done: "done", active: "in progress", waiting: "" }[state];
  return (
    <li className={`flex gap-4 ${last ? "" : "pb-[22px]"}`}>
      <div className="flex flex-col items-center">
        <StepIcon state={state} />
        {!last && (
          <span aria-hidden="true" className={`mt-1 w-0.5 flex-1 ${state === "done" ? "bg-court" : "bg-line"}`} />
        )}
      </div>
      <div className="pt-[3px]">
        <p className={`m-0 text-[17px] font-semibold ${state === "waiting" ? "text-muted" : ""}`}>
          {title}
          {status && (
            <span className={`font-medium ${state === "done" ? "text-check-ink" : "text-muted"}`}> · {status}</span>
          )}
        </p>
        <p className="mt-0.5 mb-0 text-[15px] text-muted">{detail}</p>
      </div>
    </li>
  );
}

function Working({ run, question }: { run: RunState; question: string }) {
  const order = ["writing", "running", "checking"];
  const at = order.indexOf(run.phase);
  const state = (i: number): StepState => (i < at ? "done" : i === at ? "active" : "waiting");
  return (
    <section aria-labelledby="working" className="flex flex-col gap-7 rounded-[14px] border border-line bg-white p-6 sm:p-8">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 id="working" className="m-0 font-display text-[28px] font-extrabold">
          Working on it
        </h2>
        <div className="flex items-center gap-4">
          {run.startedAt > 0 && <Elapsed since={run.startedAt} />}
          <button type="button" className={secondary} onClick={() => stopRun(question)}>
            Stop
          </button>
        </div>
      </div>
      <ol className="m-0 flex list-none flex-col p-0" aria-live="polite">
        <Step
          state={state(0)}
          title={run.retries ? "Rewriting the query" : "Writing the query"}
          detail={
            run.retries
              ? "The first query didn't run, so the model is fixing it."
              : "Turning your question into SQL against the games, players and box-score tables."
          }
        />
        <Step state={state(1)} title="Running it on the data" detail="Read-only, on every game since 2015-16." />
        <Step
          state={state(2)}
          title="Writing the answer and checking every number"
          detail="If a number isn't in the result rows, the answer doesn't go out."
          last
        />
      </ol>
      {run.sql && (
        <div className="flex flex-col gap-2.5 border-t border-line pt-5">
          <h3 className={label}>The query so far</h3>
          <Sql sql={run.sql} />
        </div>
      )}
    </section>
  );
}

// --- the result -----------------------------------------------------------------------

const KEYWORDS = new Set(
  ("select from where join left inner on and or not in is null as group by order having limit " +
    "with case when then else end distinct union all between like desc asc count sum avg min max " +
    "round cast over partition row_number rank filter coalesce exists using")
    .split(" "),
);

function Sql({ sql }: { sql: string }) {
  const parts = sql.split(/('(?:[^']|'')*'|\b[A-Za-z_]+\b)/);
  return (
    <pre className="m-0 overflow-x-auto rounded-[10px] bg-navy p-[18px] font-mono text-[13px] leading-[1.65] whitespace-pre text-line">
      {parts.map((p, i) =>
        p.startsWith("'") ? (
          <span key={i} className="text-[#9fd8b8]">{p}</span>
        ) : KEYWORDS.has(p.toLowerCase()) ? (
          <span key={i} className="text-sun">{p}</span>
        ) : (
          p
        ),
      )}
    </pre>
  );
}

function AnswerText({ text, spans, mode }: { text: string; spans: AskResult["number_spans"]; mode: "checked" | "draft" }) {
  const out: React.ReactNode[] = [];
  let at = 0;
  spans.forEach((s, i) => {
    out.push(text.slice(at, s.start));
    const n = text.slice(s.start, s.end);
    if (s.in_rows)
      out.push(<mark key={i} className="rounded bg-sun-soft px-1 font-mono text-[0.9em] text-ink">{n}</mark>);
    else if (mode === "draft")
      out.push(
        <del key={i} className="rounded bg-miss px-1 font-mono text-miss-ink" title="Not in the result rows">
          {n}
        </del>,
      );
    else out.push(n);
    at = s.end;
  });
  out.push(text.slice(at));
  return <>{out}</>;
}

function cellText(c: Cell) {
  return c === null ? "—" : String(c);
}

function toCsv(columns: string[], rows: Cell[][]) {
  const quote = (v: Cell) => {
    const s = v === null ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [columns, ...rows].map((r) => r.map(quote).join(",")).join("\n");
}

function Rows({ result, highlight }: { result: AskResult; highlight: Set<number> }) {
  const { columns, rows } = result;
  const numeric = columns.map((_, i) => rows.length > 0 && rows.every((r) => r[i] === null || typeof r[i] === "number"));
  const download = () => {
    const url = URL.createObjectURL(new Blob([toCsv(columns, rows)], { type: "text/csv" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: "fastbreak.csv" });
    a.click();
    URL.revokeObjectURL(url);
  };
  return (
    <div className="flex flex-col gap-3">
      <h3 className={label}>
        Result rows{" "}
        <span className="font-sans font-medium tracking-normal normal-case">
          · {rows.length}
          {result.truncated ? "+ (first 200 shown)" : ""} {rows.length === 1 ? "row" : "rows"}
        </span>
      </h3>
      {rows.length === 0 ? (
        <p className="m-0 text-muted">The query returned no rows.</p>
      ) : (
        <div className="max-h-[480px] overflow-auto rounded-[10px] border border-line">
          <table className="w-full border-collapse text-[15px]">
            <thead className="sticky top-0 bg-chalk">
              <tr>
                {columns.map((c, i) => (
                  <th
                    key={i}
                    scope="col"
                    className={`px-3.5 py-2.5 font-mono text-[13px] font-medium text-muted ${numeric[i] ? "text-right" : "text-left"}`}
                  >
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, ri) => (
                <tr key={ri} className="border-t border-line">
                  {r.map((c, ci) => (
                    <td key={ci} className={`px-3.5 py-2.5 ${numeric[ci] ? "text-right font-mono" : ""}`}>
                      {typeof c === "number" && highlight.has(c) ? (
                        <span className="rounded bg-sun-soft px-1">{cellText(c)}</span>
                      ) : (
                        cellText(c)
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {rows.length > 0 && (
        <button type="button" className={`${secondary} self-start`} onClick={download}>
          Download CSV
        </button>
      )}
    </div>
  );
}

function Query({ sql }: { sql: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <h3 className={label}>The query it ran</h3>
        <button
          type="button"
          className={secondary}
          onClick={() => navigator.clipboard.writeText(sql).then(() => setCopied(true))}
        >
          {copied ? "Copied" : "Copy SQL"}
        </button>
      </div>
      <Sql sql={sql} />
      <p className="m-0 text-sm text-muted">Read-only query</p>
    </div>
  );
}

function Footer({ result }: { result: AskResult }) {
  return (
    <div className="flex flex-wrap gap-x-6 gap-y-2 border-t border-line bg-chalk px-6 py-3.5 text-sm text-muted sm:px-8">
      <span>
        Model: <span className="font-mono text-ink">{result.model}</span>
      </span>
      <span>Took {result.seconds} s</span>
      {result.sql_attempts > 1 && <span>{result.sql_attempts} query attempts</span>}
    </div>
  );
}

/** Numbers the answer used that came from the rows, to highlight the same cells. */
function usedNumbers(text: string, spans: AskResult["number_spans"]) {
  return new Set(
    spans.filter((s) => s.in_rows).map((s) => Number(text.slice(s.start, s.end).replace(/[,+]/g, ""))),
  );
}

function Result({ result, question }: { result: AskResult; question: string }) {
  if (result.error) return <QueryFailed result={result} question={question} />;
  const blocked = result.blocked;
  const text = (blocked ? result.draft_answer : result.answer) ?? "";
  const used = blocked ? new Set<number>() : usedNumbers(text, result.number_spans);
  const missing = [...new Set(result.ungrounded)].map((n) => n.toLocaleString("en-US"));

  return (
    <section aria-labelledby="answer" className="overflow-hidden rounded-[14px] border border-line bg-white">
      {blocked ? (
        <div className="flex flex-col gap-4 border-b border-line-strong bg-mist px-6 py-7 sm:px-8">
          <h2 id="answer" className="m-0 font-display text-[26px] font-bold">
            No checked answer this time
          </h2>
          <p className="m-0 max-w-[64ch] text-lg text-[#1e293b]">
            The query ran, but the reply used numbers that aren&apos;t in its result rows, so FastBreak
            didn&apos;t send it. Here&apos;s what the query found, so you can read it yourself.
          </p>
          <div className="flex flex-wrap gap-2.5">
            <button type="button" className={primary} onClick={() => restartRun(question)}>
              Try again
            </button>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-[18px] px-6 py-7 sm:px-8">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 id="answer" className={label}>
              Answer
            </h2>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-check px-3 py-1 text-sm font-semibold text-check-ink">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path d="M3 8.5l3 3 7-7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Every number checked against the rows
            </span>
          </div>
          <p className="m-0 max-w-[60ch] text-xl leading-[1.45] font-medium whitespace-pre-line sm:text-2xl">
            <AnswerText text={text} spans={result.number_spans} mode="checked" />
          </p>
          {used.size > 0 && (
            <p className="m-0 text-sm text-muted">Highlighted numbers come straight from the result rows below.</p>
          )}
        </div>
      )}

      {blocked && (
        <div className="flex flex-col gap-3.5 border-b border-line px-6 py-6 sm:px-8">
          <h3 className={label}>Why it was held back</h3>
          <div className="rounded-[10px] border border-dashed border-line-strong px-[18px] py-4">
            <p className="mt-0 mb-1.5 text-[13px] font-semibold tracking-[0.05em] text-muted uppercase">
              Unchecked draft (not sent)
            </p>
            <p className="m-0 text-[17px] whitespace-pre-line text-[#334155]">
              <AnswerText text={text} spans={result.number_spans} mode="draft" />
            </p>
          </div>
          {missing.length > 0 && (
            <p className="m-0 text-[15px] text-[#334155]">
              {missing.map((m, i) => (
                <span key={m}>
                  {i > 0 && (i === missing.length - 1 ? " and " : ", ")}
                  <strong>{m}</strong>
                </span>
              ))}{" "}
              {missing.length === 1 ? "doesn't" : "don't"} appear anywhere in the rows.
            </p>
          )}
        </div>
      )}

      <div className="flex flex-wrap">
        <div className="min-w-0 flex-[1_1_380px] border-line px-6 py-6 sm:px-8 lg:border-r">
          <Rows result={result} highlight={used} />
        </div>
        <div className="min-w-0 flex-[1_1_420px] px-6 py-6 sm:px-8">
          <Query sql={result.sql} />
        </div>
      </div>
      <Footer result={result} />
    </section>
  );
}

// --- no answer at all -----------------------------------------------------------------

function QueryFailed({ result, question }: { result: AskResult; question: string }) {
  return (
    <section aria-labelledby="qfail" className="overflow-hidden rounded-[14px] border border-line bg-white">
      <div className="flex flex-col gap-4 border-b border-line-strong bg-mist px-6 py-7 sm:px-8">
        <h2 id="qfail" className="m-0 font-display text-[26px] font-bold">
          Couldn&apos;t write a query that runs
        </h2>
        <p className="m-0 max-w-[64ch] text-lg text-[#1e293b]">
          The model tried {result.sql_attempts} {result.sql_attempts === 1 ? "time" : "times"} and the
          database refused each query. Rephrasing the question often helps.
        </p>
        <p className="m-0 font-mono text-sm text-muted">{result.error}</p>
        <div className="flex flex-wrap gap-2.5">
          <button type="button" className={primary} onClick={() => restartRun(question)}>
            Try again
          </button>
        </div>
      </div>
      {result.sql && (
        <div className="px-6 py-6 sm:px-8">
          <Query sql={result.sql} />
        </div>
      )}
      <Footer result={result} />
    </section>
  );
}

function Failed({ run, question }: { run: RunState; question: string }) {
  const stopped = run.phase === "stopped";
  return (
    <section aria-labelledby="failed" className="flex flex-col gap-4 rounded-[14px] border border-line bg-white px-6 py-7 sm:px-8">
      <h2 id="failed" className="m-0 font-display text-[26px] font-bold">
        {stopped ? "Stopped" : "No answer"}
      </h2>
      <p className="m-0 max-w-[64ch] text-lg text-[#1e293b]">
        {stopped ? "You stopped this question before it finished." : run.error}
      </p>
      <div>
        <button type="button" className={primary} onClick={() => restartRun(question)}>
          Ask again
        </button>
      </div>
    </section>
  );
}
