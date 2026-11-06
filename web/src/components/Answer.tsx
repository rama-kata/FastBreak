"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import { INITIAL, restartRun, snapshot, stopRun, subscribe, type RunState } from "@/lib/ask-store";
import type { AskResult, Cell } from "@/lib/types";

// Each answer prints like a game story: the question as the deck, the answer as the
// headline, then the box score (the rows) and how we got it (the SQL). Point at a number
// in the headline and the editor's pen rings the cells it came from.

const label = "m-0 font-agate text-[13px] font-bold uppercase tracking-[0.08em] text-ink";
const button =
  "inline-flex min-h-11 cursor-pointer items-center justify-center px-4 font-agate text-[15px] font-bold";
const secondary = `${button} border border-ink text-ink hover:bg-sheet`;
const primary = `${button} bg-ink text-paper hover:bg-ink-soft`;
const small = "inline-flex min-h-9 cursor-pointer items-center px-1 font-agate text-[13px] font-bold underline underline-offset-3 hover:decoration-2";

function useRun(question: string): RunState {
  return useSyncExternalStore(
    (listener) => subscribe(question, listener),
    () => snapshot(question),
    () => INITIAL,
  );
}

/** One question and its answer, set as one story. */
export function Exchange({ question, onAnswered }: { question: string; onAnswered: (r: AskResult) => void }) {
  const run = useRun(question);
  const result = run.phase === "done" ? run.result : null;
  useEffect(() => {
    if (result) onAnswered(result);
  }, [result, onAnswered]);

  return (
    <article className="@container flex flex-col gap-4 border-b border-rule pb-10">
      <p className="m-0 max-w-[60ch] text-[18px] leading-snug whitespace-pre-line text-ink-soft">
        <span className="sr-only">You asked: </span>
        {question}
      </p>
      {result ? (
        <Result result={result} question={question} />
      ) : run.phase === "failed" || run.phase === "stopped" ? (
        <Failed run={run} question={question} />
      ) : (
        <Working run={run} question={question} />
      )}
    </article>
  );
}

function Headline({ children, length }: { children: React.ReactNode; length: number }) {
  const size =
    length > 220 ? "text-[22px] sm:text-[26px]" : length > 120 ? "text-[26px] sm:text-[32px]" : "text-[30px] sm:text-[44px]";
  return (
    <h2 className={`m-0 max-w-[30ch] font-extrabold leading-[1.06] tracking-[-0.025em] text-balance whitespace-pre-line ${size}`}>
      {children}
    </h2>
  );
}

function clock(ms: number) {
  const s = Math.max(0, Math.floor(ms / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

// --- while it works: the play-by-play --------------------------------------------------

function Elapsed({ since }: { since: number }) {
  const [now, setNow] = useState(since);
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  return <span className="font-agate text-[15px] font-bold">{clock(now - since)}</span>;
}

function Working({ run, question }: { run: RunState; question: string }) {
  const now =
    run.phase === "writing"
      ? run.retries
        ? "Rewriting the query after an error"
        : run.route === "hard"
          ? "Thinking through a hard one: about a minute"
          : "Writing the query"
      : run.phase === "running"
        ? "Running it on every game since 2015-16"
        : "Writing the answer and checking every number";
  return (
    <div className="flex flex-col gap-4">
      <Headline length={now.length}>
        <span className="text-muted">{now}…</span>
      </Headline>
      <div className="flex items-center justify-between gap-3 border-t-2 border-ink pt-2">
        <span className="flex items-center gap-2 font-agate text-[14px] text-muted">
          <span aria-hidden="true" className="size-2 animate-pulse rounded-full bg-spot motion-reduce:animate-none" />
          Live
        </span>
        <div className="flex items-center gap-4">
          {run.startedAt > 0 && <Elapsed since={run.startedAt} />}
          <button type="button" className={secondary} onClick={() => stopRun(question)}>
            Stop
          </button>
        </div>
      </div>
      <ol aria-live="polite" className="m-0 flex max-w-[640px] list-none flex-col p-0 font-agate text-[15px] [&>li:last-child]:border-b-0">
        <li className="grid grid-cols-[3.5rem_1fr] border-b border-rule py-1.5">
          <span className="text-muted">0:00</span>Question received
        </li>
        {run.plays.map((p, i) => (
          <li key={i} className="grid grid-cols-[3.5rem_1fr] border-b border-rule py-1.5">
            <span className="text-muted">{clock(p.at - run.startedAt)}</span>
            {p.text}
          </li>
        ))}
      </ol>
      {run.sql && (
        <details>
          <summary className={`${small} list-none`}>The query so far</summary>
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

function SqlLine({ line: raw }: { line: string }) {
  // A wrapped line continues 2ch deeper than its own indent, so the nesting stays readable.
  const indent = raw.length - raw.trimStart().length;
  const line = raw.trimStart();
  const parts = line.split(/('(?:[^']|'')*'|\b[A-Za-z_]+\b)/);
  return (
    <span className="block -indent-[2ch]" style={{ paddingLeft: `${indent + 2}ch` }}>
      {parts.map((p, i) =>
        p.startsWith("'") ? (
          <span key={i} className="italic">{p}</span>
        ) : KEYWORDS.has(p.toLowerCase()) ? (
          <span key={i} className="font-bold text-ink">{p}</span>
        ) : (
          p
        ),
      )}
      {line === "" && "\u00a0"}
    </span>
  );
}

/** The SQL, wrapped rather than scrolled sideways: a long line continues indented under itself. */
function Sql({ sql }: { sql: string }) {
  return (
    <pre className="m-0 max-h-[420px] overflow-y-auto border border-rule bg-sheet p-4 font-mono text-[12.5px] leading-[1.65] break-words whitespace-pre-wrap text-ink-soft">
      {sql.split("\n").map((line, i) => (
        <SqlLine key={i} line={line} />
      ))}
    </pre>
  );
}

/** The editor's pen: an open, slightly tilted ellipse, drawn on around a number. */
function PenRing() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 100 40"
      preserveAspectRatio="none"
      className="pen-ring pointer-events-none absolute top-[-0.02em] left-[-0.26em] h-[calc(100%+0.04em)] w-[calc(100%+0.52em)] -rotate-2 overflow-visible"
    >
      <path
        pathLength={1}
        d="M80 5 C 60 -1, 16 1, 5 15 C -4 28, 22 40, 54 38 C 84 36, 100 27, 95 14 C 91 5, 72 2, 58 4"
        fill="none"
        stroke="var(--color-spot)"
        strokeWidth="2"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

const asNumber = (s: string) => Number(s.replace(/[,+]/g, ""));

function AnswerText({
  text,
  spans,
  mode,
  onPoint,
  ringed,
}: {
  text: string;
  spans: AskResult["number_spans"];
  mode: "checked" | "draft";
  onPoint?: (n: number | null) => void;
  ringed?: number | null;
}) {
  const out: React.ReactNode[] = [];
  let at = 0;
  spans.forEach((s, i) => {
    out.push(text.slice(at, s.start));
    const n = text.slice(s.start, s.end);
    if (s.in_rows && onPoint) {
      const value = asNumber(n);
      out.push(
        <mark
          key={i}
          tabIndex={0}
          onMouseEnter={() => onPoint(value)}
          onMouseLeave={() => onPoint(null)}
          onFocus={() => onPoint(value)}
          onBlur={() => onPoint(null)}
          title="Show where this number is in the box score"
          className={`relative mx-[0.15em] inline-block cursor-help bg-transparent text-inherit decoration-spot decoration-2 underline-offset-[0.14em] focus-visible:outline-none ${ringed === value ? "no-underline" : "underline"}`}
        >
          {n}
          {ringed === value && <PenRing />}
        </mark>,
      );
    } else if (mode === "draft" && !s.grounded)
      out.push(
        <del key={i} className="font-bold text-spot decoration-2" title="Not in the result rows">
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

function BoxScore({ result, used, ringed }: { result: AskResult; used: Set<number>; ringed: number | null }) {
  const { columns, rows } = result;
  const numeric = columns.map((_, i) => rows.length > 0 && rows.every((r) => r[i] === null || typeof r[i] === "number"));
  const download = () => {
    const url = URL.createObjectURL(new Blob([toCsv(columns, rows)], { type: "text/csv" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: "fastbreak.csv" });
    a.click();
    URL.revokeObjectURL(url);
  };
  return (
    <section className="flex min-w-0 flex-col gap-1.5">
      <div className="flex items-center justify-between gap-3 border-b-2 border-ink">
        <h3 className={label}>
          Box score: what the query returned
          {result.truncated && <span className="font-normal tracking-normal normal-case"> · first 200 rows</span>}
        </h3>
        {rows.length > 0 && (
          <button type="button" className={small} onClick={download}>
            CSV
          </button>
        )}
      </div>
      {rows.length === 0 ? (
        <p className="m-0 py-2 font-agate text-[15px] text-muted">The query returned no rows.</p>
      ) : (
        <div className="max-h-[360px] overflow-auto">
          <table className="w-auto min-w-[16rem] border-collapse font-agate text-[15px]">
            <thead className="sticky top-0 bg-paper">
              <tr className="border-b border-rule">
                {columns.map((c, i) => (
                  <th
                    key={i}
                    scope="col"
                    className={`px-3 py-1.5 text-[11.5px] font-bold tracking-[0.06em] uppercase ${numeric[i] ? "text-right" : "text-left"}`}
                  >
                    {c.replace(/_/g, " ")}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, ri) => (
                <tr key={ri} className="border-b border-rule">
                  {r.map((c, ci) => (
                    <td key={ci} className={`px-3 py-1.5 ${numeric[ci] ? "text-right" : ""}`}>
                      {typeof c === "number" && used.has(c) ? (
                        <span className="relative mx-[0.15em] inline-block font-bold">
                          {cellText(c)}
                          {ringed === c && <PenRing />}
                        </span>
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
    </section>
  );
}

function Query({ sql }: { sql: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <section className="flex min-w-0 flex-col gap-1.5 @3xl:border-l @3xl:border-rule @3xl:pl-8">
      <div className="flex items-center justify-between gap-3 border-b-2 border-ink">
        <h3 className={label}>How we got it · read-only query</h3>
        <button type="button" className={small} onClick={() => navigator.clipboard.writeText(sql).then(() => setCopied(true))}>
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <div className="pt-1">
        <Sql sql={sql} />
      </div>
    </section>
  );
}

function Proof({ result, used, ringed }: { result: AskResult; used: Set<number>; ringed: number | null }) {
  return (
    <div className="grid gap-8 @3xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      <BoxScore result={result} used={used} ringed={ringed} />
      <Query sql={result.sql} />
    </div>
  );
}

function Dateline({ result, status }: { result: AskResult; status: React.ReactNode }) {
  const n = result.rows.length;
  return (
    <div className="flex flex-col gap-1 border-t-2 border-ink pt-2 font-agate text-[14px] text-ink-soft">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <span>{status}</span>
        <span>
          {n}
          {result.truncated ? "+" : ""} {n === 1 ? "row" : "rows"} · {result.seconds} s
          {result.sql_attempts > 1 ? ` · ${result.sql_attempts} query attempts` : ""}
        </span>
      </div>
      {result.queued_for_review && (
        <span className="text-muted">
          A hard question like this one gets a second look from a person, after the answer has gone out.
        </span>
      )}
    </div>
  );
}

/** Numbers the answer used that came from the rows, to mark the same cells. */
function usedNumbers(text: string, spans: AskResult["number_spans"]) {
  return new Set(spans.filter((s) => s.in_rows).map((s) => asNumber(text.slice(s.start, s.end))));
}

function Result({ result, question }: { result: AskResult; question: string }) {
  const [ringed, setRinged] = useState<number | null>(null);
  if (result.error) return <QueryFailed result={result} question={question} />;

  if (result.blocked) {
    const missing = [...new Set(result.ungrounded)].map(String); // as written: years stay 2015
    return (
      <div className="flex flex-col gap-5">
        <Headline length={30}>No checked answer this time</Headline>
        <p className="m-0 max-w-[62ch] text-[16px] leading-relaxed text-ink-soft">
          The reply used{" "}
          {missing.map((m, i) => (
            <span key={m}>
              {i > 0 && (i === missing.length - 1 ? " and " : ", ")}
              <strong className="text-ink">{m}</strong>
            </span>
          ))}
          , which {missing.length === 1 ? "isn't" : "aren't"} in the query&apos;s result rows, so FastBreak held it
          back. The rows and the query are below, so you can read them yourself.
        </p>
        <div className="max-w-[62ch] border border-dashed border-ink px-4 py-3">
          <p className="mt-0 mb-1 font-agate text-[12px] font-bold tracking-[0.08em] uppercase">The draft it held back</p>
          <p className="m-0 text-[15px] whitespace-pre-line text-ink-soft">
            <AnswerText text={result.draft_answer ?? ""} spans={result.number_spans} mode="draft" />
          </p>
        </div>
        <div>
          <button type="button" className={primary} onClick={() => restartRun(question)}>
            Try again
          </button>
        </div>
        <Dateline result={result} status="Held back: a number wasn't in the rows" />
        <Proof result={result} used={new Set()} ringed={null} />
      </div>
    );
  }

  const text = result.answer ?? "";
  return (
    <div className="flex flex-col gap-5">
      <Headline length={text.length}>
        <AnswerText text={text} spans={result.number_spans} mode="checked" onPoint={setRinged} ringed={ringed} />
      </Headline>
      <Dateline
        result={result}
        status={
          <span className="inline-flex items-center gap-1.5 font-bold text-ink">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path d="M3 8.5l3 3 7-7" stroke="currentColor" strokeWidth="2.2" strokeLinecap="square" />
            </svg>
            Every number checked against the rows
          </span>
        }
      />
      <Proof result={result} used={usedNumbers(text, result.number_spans)} ringed={ringed} />
    </div>
  );
}

// --- no answer at all -----------------------------------------------------------------

function QueryFailed({ result, question }: { result: AskResult; question: string }) {
  return (
    <div className="flex flex-col gap-4">
      <Headline length={40}>Couldn&apos;t write a query that runs</Headline>
      <p className="m-0 max-w-[62ch] text-[16px] text-ink-soft">
        The model tried {result.sql_attempts} {result.sql_attempts === 1 ? "time" : "times"} and the database
        refused the query. Rephrasing the question often helps.
      </p>
      <p className="m-0 font-mono text-[12.5px] break-words text-muted">{result.error}</p>
      <div>
        <button type="button" className={primary} onClick={() => restartRun(question)}>
          Try again
        </button>
      </div>
      {result.sql && (
        <details>
          <summary className={`${small} list-none`}>The query it tried</summary>
          <div className="mt-2">
            <Sql sql={result.sql} />
          </div>
        </details>
      )}
    </div>
  );
}

function Failed({ run, question }: { run: RunState; question: string }) {
  const stopped = run.phase === "stopped";
  return (
    <div className="flex flex-col gap-4">
      <Headline length={10}>{stopped ? "Stopped" : "No answer"}</Headline>
      <p className="m-0 max-w-[62ch] text-[16px] text-ink-soft">
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
