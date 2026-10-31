"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import { INITIAL, restartRun, snapshot, stopRun, subscribe, type RunState } from "@/lib/ask-store";
import type { AskResult, Cell } from "@/lib/types";

const label = "m-0 font-display text-[13px] font-bold uppercase tracking-[0.06em] text-muted";
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

/** One question and its answer, as a pair of chat messages. */
export function Exchange({ question, onAnswered }: { question: string; onAnswered: (r: AskResult) => void }) {
  const run = useRun(question);
  const result = run.phase === "done" ? run.result : null;
  useEffect(() => {
    if (result) onAnswered(result);
  }, [result, onAnswered]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-end">
        <p className="m-0 max-w-[85%] rounded-2xl rounded-br-md bg-navy px-4 py-3 text-[16px] whitespace-pre-line text-white sm:max-w-[70%]">
          {question}
        </p>
      </div>
      <div className="flex items-start gap-3">
        {/* eslint-disable-next-line @next/next/no-img-element -- a 96px decorative avatar */}
        <img src="/avatar.png" alt="" width={40} height={40} className="mt-1 size-10 shrink-0 rounded-full bg-night" />
        <div className="min-w-0 flex-1">
          {result ? (
            <Result result={result} question={question} />
          ) : run.phase === "failed" || run.phase === "stopped" ? (
            <Failed run={run} question={question} />
          ) : (
            <Working run={run} question={question} />
          )}
        </div>
      </div>
    </div>
  );
}

const bubble = "rounded-2xl rounded-tl-md border border-line bg-white";

// --- while it works -------------------------------------------------------------------

function Elapsed({ since }: { since: number }) {
  const [now, setNow] = useState(since);
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  const s = Math.max(0, Math.floor((now - since) / 1000));
  return (
    <span className="font-mono text-sm text-muted">
      {Math.floor(s / 60)}:{String(s % 60).padStart(2, "0")}
    </span>
  );
}

type StepState = "done" | "active" | "waiting";

function StepIcon({ state }: { state: StepState }) {
  if (state === "done")
    return (
      <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-court">
        <svg width="12" height="12" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <path d="M3 8.5l3 3 7-7" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
    );
  if (state === "active")
    return (
      <span className="size-6 shrink-0 animate-spin rounded-full border-[3px] border-sun border-t-navy motion-reduce:animate-none" />
    );
  return <span className="size-6 shrink-0 rounded-full border-2 border-line-strong" />;
}

function Step({ state, children }: { state: StepState; children: React.ReactNode }) {
  return (
    <li className="flex items-center gap-3">
      <StepIcon state={state} />
      <span className={state === "waiting" ? "text-muted" : "font-medium"}>
        {children}
        {state === "active" && <span className="sr-only"> (in progress)</span>}
        {state === "done" && <span className="sr-only"> (done)</span>}
      </span>
    </li>
  );
}

function Working({ run, question }: { run: RunState; question: string }) {
  const at = ["writing", "running", "checking"].indexOf(run.phase);
  const state = (i: number): StepState => (i < at ? "done" : i === at ? "active" : "waiting");
  return (
    <div className={`${bubble} flex flex-col gap-4 px-5 py-4`}>
      <div className="flex items-center justify-between gap-3">
        <p className="m-0 font-semibold">Working on it</p>
        <div className="flex items-center gap-3">
          {run.startedAt > 0 && <Elapsed since={run.startedAt} />}
          <button type="button" className={secondary} onClick={() => stopRun(question)}>
            Stop
          </button>
        </div>
      </div>
      <ol className="m-0 flex list-none flex-col gap-2.5 p-0 text-[15px]" aria-live="polite">
        <Step state={state(0)}>
          {run.retries
            ? "Fixing the query after an error"
            : run.route === "hard"
              ? "Writing the query. It's a hard one, so it's thinking it through (about a minute)"
              : "Writing the query"}
        </Step>
        <Step state={state(1)}>Running it on every game since 2015-16</Step>
        <Step state={state(2)}>Writing the answer and checking every number</Step>
      </ol>
      {run.sql && (
        <details className="group">
          <summary className="cursor-pointer text-sm font-semibold text-court-ink">The query so far</summary>
          <div className="mt-2">
            <Sql sql={run.sql} />
          </div>
        </details>
      )}
    </div>
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
    <pre className="m-0 overflow-x-auto rounded-[10px] bg-navy p-4 font-mono text-[13px] leading-[1.65] whitespace-pre text-line">
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
      out.push(<mark key={i} className="rounded bg-sun-soft px-1 font-mono text-[0.92em] text-ink">{n}</mark>);
    else if (mode === "draft" && !s.grounded)
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
    <div className="flex flex-col gap-2.5">
      <div className="flex items-center justify-between gap-3">
        <h3 className={label}>
          Result rows{" "}
          <span className="font-sans font-medium tracking-normal normal-case">
            · {rows.length}
            {result.truncated ? "+ (first 200 shown)" : ""}
          </span>
        </h3>
        {rows.length > 0 && (
          <button type="button" className={secondary} onClick={download}>
            Download CSV
          </button>
        )}
      </div>
      {rows.length === 0 ? (
        <p className="m-0 text-muted">The query returned no rows.</p>
      ) : (
        <div className="max-h-[360px] overflow-auto rounded-[10px] border border-line">
          <table className="w-full border-collapse text-[15px]">
            <thead className="sticky top-0 bg-chalk">
              <tr>
                {columns.map((c, i) => (
                  <th
                    key={i}
                    scope="col"
                    className={`px-3 py-2 font-mono text-[12px] font-medium text-muted ${numeric[i] ? "text-right" : "text-left"}`}
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
                    <td key={ci} className={`px-3 py-2 ${numeric[ci] ? "text-right font-mono" : ""}`}>
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
    </div>
  );
}

function Query({ sql }: { sql: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex items-center justify-between gap-3">
        <h3 className={label}>The query it ran · read-only</h3>
        <button
          type="button"
          className={secondary}
          onClick={() => navigator.clipboard.writeText(sql).then(() => setCopied(true))}
        >
          {copied ? "Copied" : "Copy SQL"}
        </button>
      </div>
      <Sql sql={sql} />
    </div>
  );
}

function Proof({ result, highlight, summary, open }: { result: AskResult; highlight: Set<number>; summary: string; open?: boolean }) {
  return (
    <details open={open} className="group border-t border-line">
      <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 px-5 text-sm font-semibold text-court-ink hover:bg-chalk [&::-webkit-details-marker]:hidden">
        <span>{summary}</span>
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true" className="transition-transform group-open:rotate-180">
          <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </summary>
      <div className="flex flex-col gap-5 px-5 pt-1 pb-5">
        <Rows result={result} highlight={highlight} />
        <Query sql={result.sql} />
      </div>
    </details>
  );
}

function Meta({ result }: { result: AskResult }) {
  return (
    <>
      <p className="m-0 mt-1.5 pl-1 text-[13px] text-muted">
        <span className="font-mono">{result.model}</span>
        {result.route ? ` · ${result.route} question` : ""} · {result.seconds} s
        {result.sql_attempts > 1 ? ` · ${result.sql_attempts} query attempts` : ""}
      </p>
      {result.queued_for_review && (
        <p className="m-0 mt-1 pl-1 text-[13px] text-muted">
          A hard question like this one gets a second look from a person, who checks the answer
          after it&apos;s been sent.
        </p>
      )}
    </>
  );
}

/** Numbers the answer used that came from the rows, to highlight the same cells. */
function usedNumbers(text: string, spans: AskResult["number_spans"]) {
  return new Set(
    spans.filter((s) => s.in_rows).map((s) => Number(text.slice(s.start, s.end).replace(/[,+]/g, ""))),
  );
}

function proofSummary(result: AskResult) {
  const n = result.rows.length;
  return `See the proof · ${n}${result.truncated ? "+" : ""} ${n === 1 ? "row" : "rows"} and the SQL`;
}

function Result({ result, question }: { result: AskResult; question: string }) {
  if (result.error) return <QueryFailed result={result} question={question} />;

  if (result.blocked) {
    const missing = [...new Set(result.ungrounded)].map(String); // as written: years stay 2015
    return (
      <>
        <div className={`${bubble} overflow-hidden`}>
          <div className="flex flex-col gap-3 px-5 py-4">
            <p className="m-0 font-semibold">No checked answer this time</p>
            <p className="m-0 text-[15px] text-[#1e293b]">
              The reply used{" "}
              {missing.map((m, i) => (
                <span key={m}>
                  {i > 0 && (i === missing.length - 1 ? " and " : ", ")}
                  <strong>{m}</strong>
                </span>
              ))}
              , which {missing.length === 1 ? "isn't" : "aren't"} in the query&apos;s result rows, so
              FastBreak held it back. The rows and query are below so you can read them yourself.
            </p>
            <div className="rounded-[10px] border border-dashed border-line-strong px-4 py-3">
              <p className="mt-0 mb-1 text-[12px] font-semibold tracking-[0.05em] text-muted uppercase">
                Unchecked draft (not sent)
              </p>
              <p className="m-0 text-[15px] whitespace-pre-line text-[#334155]">
                <AnswerText text={result.draft_answer ?? ""} spans={result.number_spans} mode="draft" />
              </p>
            </div>
            <div>
              <button type="button" className={primary} onClick={() => restartRun(question)}>
                Try again
              </button>
            </div>
          </div>
          <Proof result={result} highlight={new Set()} summary={`What the query found · ${result.rows.length} rows and the SQL`} open />
        </div>
        <Meta result={result} />
      </>
    );
  }

  const text = result.answer ?? "";
  return (
    <>
      <div className={`${bubble} overflow-hidden`}>
        <div className="flex flex-col gap-3 px-5 py-4">
          <span className="inline-flex items-center gap-1.5 self-start rounded-full bg-check px-2.5 py-0.5 text-[13px] font-semibold text-check-ink">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path d="M3 8.5l3 3 7-7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Checked against the rows
          </span>
          <p className="m-0 text-[17px] leading-relaxed whitespace-pre-line">
            <AnswerText text={text} spans={result.number_spans} mode="checked" />
          </p>
        </div>
        <Proof result={result} highlight={usedNumbers(text, result.number_spans)} summary={proofSummary(result)} />
      </div>
      <Meta result={result} />
    </>
  );
}

// --- no answer at all -----------------------------------------------------------------

function QueryFailed({ result, question }: { result: AskResult; question: string }) {
  return (
    <>
      <div className={`${bubble} overflow-hidden`}>
        <div className="flex flex-col gap-3 px-5 py-4">
          <p className="m-0 font-semibold">Couldn&apos;t write a query that runs</p>
          <p className="m-0 text-[15px] text-[#1e293b]">
            The model tried {result.sql_attempts} {result.sql_attempts === 1 ? "time" : "times"} and the
            database refused the query. Rephrasing the question often helps.
          </p>
          <p className="m-0 font-mono text-[13px] break-words text-muted">{result.error}</p>
          <div>
            <button type="button" className={primary} onClick={() => restartRun(question)}>
              Try again
            </button>
          </div>
        </div>
        {result.sql && (
          <details className="border-t border-line">
            <summary className="flex min-h-12 cursor-pointer items-center px-5 text-sm font-semibold text-court-ink">
              The query it tried
            </summary>
            <div className="px-5 pb-5">
              <Sql sql={result.sql} />
            </div>
          </details>
        )}
      </div>
      <Meta result={result} />
    </>
  );
}

function Failed({ run, question }: { run: RunState; question: string }) {
  const stopped = run.phase === "stopped";
  return (
    <div className={`${bubble} flex flex-col gap-3 px-5 py-4`}>
      <p className="m-0 font-semibold">{stopped ? "Stopped" : "No answer"}</p>
      <p className="m-0 text-[15px] text-[#1e293b]">
        {stopped ? "You stopped this question before it finished." : run.error}
      </p>
      <div>
        <button type="button" className={primary} onClick={() => restartRun(question)}>
          Ask again
        </button>
      </div>
    </div>
  );
}
