"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { seedRun } from "@/lib/ask-store";
import { history as historyStore, type HistoryItem } from "@/lib/history";
import type { AskResult } from "@/lib/types";
import { Exchange } from "./Answer";
import { AccuracyLine, HowItWorksPanel } from "./HowItWorks";

const MAX_CHARS = 300; // the API's limit

const SUGGESTIONS = [
  "Who made the most three-pointers from 2015-16 to 2025-26?",
  "What was the Warriors' regular season record in 2015-16?",
  "How many points did Klay Thompson score on December 5, 2016?",
];

function Flag({ size }: { size: "lg" | "sm" }) {
  return (
    <span className={`font-black tracking-[-0.035em] ${size === "lg" ? "text-[36px] leading-none" : "text-[24px] leading-none"}`}>
      Fast<span className="text-spot">Break</span>
    </span>
  );
}

function HistoryList({
  items,
  active,
  onPick,
  onClear,
}: {
  items: HistoryItem[];
  active: string | undefined;
  onPick: (item: HistoryItem) => void;
  onClear: () => void;
}) {
  return (
    <nav aria-labelledby="history-heading" className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center justify-between border-b border-ink">
        <h2 id="history-heading" className="m-0 py-1 font-agate text-[13px] font-bold tracking-[0.1em] uppercase">
          Your questions
        </h2>
        {items.length > 0 && (
          <button
            type="button"
            onClick={onClear}
            className="min-h-8 cursor-pointer px-1 font-agate text-[13px] text-muted underline underline-offset-3 hover:text-ink hover:decoration-2"
          >
            Clear
          </button>
        )}
      </div>
      {items.length === 0 ? (
        <p className="m-0 pt-2.5 text-[14px] leading-snug text-muted">
          Questions you ask show up here, kept in this browser only.
        </p>
      ) : (
        <ul className="m-0 flex list-none flex-col overflow-y-auto p-0">
          {items.map((item) => (
            <li key={item.question} className="border-b border-rule">
              <button
                type="button"
                onClick={() => onPick(item)}
                aria-current={item.question === active ? "true" : undefined}
                className={`line-clamp-2 w-full cursor-pointer py-2.5 text-left text-[14px] leading-snug text-ink underline-offset-3 hover:underline ${item.question === active ? "font-bold" : ""}`}
                title={item.question}
              >
                {item.question}
              </button>
            </li>
          ))}
        </ul>
      )}
    </nav>
  );
}

export function ChatApp({ games, freshness }: { games: React.ReactNode; freshness: React.ReactNode }) {
  const [thread, setThread] = useState<{ id: number; question: string }[]>([]);
  const history = useSyncExternalStore(
    historyStore.subscribe,
    historyStore.snapshot,
    historyStore.serverSnapshot,
  );
  const [draft, setDraft] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [howOpen, setHowOpen] = useState(false);
  const nextId = useRef(1);
  const threadEnd = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const ask = useCallback((question: string) => {
    const q = question.trim().slice(0, MAX_CHARS);
    if (!q) return;
    setThread((t) => [...t, { id: nextId.current++, question: q }]);
    setDraft("");
    setMenuOpen(false);
  }, []);

  // "Ask about it" on a game card links to /?q=...: ask it, then tidy the address bar.
  const linked = searchParams.get("q");
  useEffect(() => {
    if (!linked) return;
    ask(linked);
    router.replace(pathname, { scroll: false });
  }, [linked, ask, router, pathname]);

  // A new question scrolls to its own top, so the headline answer lands in view, not the SQL.
  useEffect(() => {
    threadEnd.current?.previousElementSibling?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [thread.length]);

  const onAnswered = useCallback((result: AskResult) => {
    historyStore.save({ question: result.question, at: Date.now(), result });
  }, []);

  const openFromHistory = (item: HistoryItem) => {
    seedRun(item.question, item.result);
    setThread((t) => [...t, { id: nextId.current++, question: item.question }]);
    setMenuOpen(false);
  };

  const newChat = () => {
    setThread([]);
    setMenuOpen(false);
    input.current?.focus();
  };

  const masthead = (
      <div className="flex flex-col gap-1.5 border-b-4 border-double border-ink pb-2.5">
        <button
          type="button"
          onClick={newChat}
          className="flex cursor-pointer items-end justify-between gap-2 text-left text-ink"
          aria-label="FastBreak, start a new question"
        >
          <Flag size="lg" />
          {/* eslint-disable-next-line @next/next/no-img-element -- static brand art */}
          <img src="/mascot-cut.png" alt="" width={86} height={64} className="-mb-1 h-[52px] w-auto" />
        </button>
        <div className="font-agate text-[13px] text-ink-soft">{freshness}</div>
      </div>
  );

  const railBody = (
    <>
      <button type="button" onClick={newChat} className="flex min-h-11 cursor-pointer items-center gap-2.5 bg-ink px-4 font-agate text-[16px] font-bold text-paper hover:bg-ink-soft">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
          <path d="M7 1v12M1 7h12" stroke="currentColor" strokeWidth="2" />
        </svg>
        New question
      </button>
      <HistoryList items={history} active={thread.at(-1)?.question} onPick={openFromHistory} onClear={historyStore.clear} />
      <p className="m-0 border-t border-rule pt-3 text-[17px] leading-tight font-extrabold tracking-[-0.01em]">
        Ask anything. See the proof.
      </p>
    </>
  );

  return (
    <div className="flex h-dvh flex-col bg-paper md:flex-row">
      {/* Phone: the flag across the top, with Your questions in a drawer */}
      <header className="flex items-center justify-between gap-3 border-b-4 border-double border-ink px-4 py-2 md:hidden">
        <button type="button" onClick={newChat} className="flex items-center gap-2 text-ink" aria-label="FastBreak, start a new question">
          {/* eslint-disable-next-line @next/next/no-img-element -- static brand art */}
          <img src="/mascot-cut.png" alt="" width={54} height={40} className="h-10 w-auto" />
          <Flag size="sm" />
        </button>
        <button
          type="button"
          onClick={() => setMenuOpen((o) => !o)}
          aria-expanded={menuOpen}
          aria-controls="phone-menu"
          className="flex min-h-11 cursor-pointer items-center px-2 font-agate text-[15px] font-bold underline underline-offset-3"
        >
          {menuOpen ? "Close" : "Your questions"}
        </button>
      </header>
      {menuOpen && (
        <div id="phone-menu" className="flex max-h-[70dvh] flex-col gap-5 overflow-y-auto border-b border-rule px-4 pt-3 pb-5 md:hidden">
          <div className="font-agate text-[13px] text-ink-soft">{freshness}</div>
          {railBody}
        </div>
      )}

      <aside className="hidden w-[280px] shrink-0 flex-col gap-6 overflow-y-auto border-r border-rule px-5 pt-6 pb-5 md:flex">
        {masthead}
        {railBody}
      </aside>

      <main className={`flex min-h-0 min-w-0 flex-1 flex-col ${howOpen ? "lg:pr-[460px]" : ""}`}>
        {games}
        <div className="min-h-0 flex-1 overflow-y-auto">
          {thread.length === 0 ? (
            <div className="mx-auto grid max-w-[1120px] gap-x-12 gap-y-10 px-5 pt-10 pb-12 sm:px-10 sm:pt-14 lg:grid-cols-[minmax(0,1fr)_300px]">
              <section className="flex flex-col gap-6">
                <h1 className="m-0 max-w-[13ch] text-[clamp(44px,6.4vw,92px)] leading-[0.94] font-black tracking-[-0.04em] text-balance">
                  Ask anything about the NBA. <span className="text-spot">See the proof.</span>
                </h1>
                <p className="m-0 max-w-[44ch] border-t border-ink pt-3 text-[20px] leading-snug text-ink-soft">
                  Plain-English questions about every game since 2015-16. Each answer shows the query it ran and
                  the rows it came from.
                </p>
              </section>
              <section aria-labelledby="try-one" className="flex flex-col self-end">
                <h2 id="try-one" className="m-0 border-b-2 border-ink pb-1 font-agate text-[13px] font-bold tracking-[0.1em] uppercase">
                  Try one
                </h2>
                <ul className="m-0 flex list-none flex-col p-0">
                  {SUGGESTIONS.map((s) => (
                    <li key={s} className="border-b border-rule">
                      <button
                        type="button"
                        onClick={() => ask(s)}
                        className="group grid min-h-12 w-full cursor-pointer grid-cols-[1fr_auto] items-center gap-3 py-3 text-left text-[16px] leading-snug text-ink underline-offset-3 hover:underline"
                      >
                        {s}
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true" className="transition-transform duration-200 ease-out group-hover:translate-x-1">
                          <path d="M2 8h11M9 4l4 4-4 4" stroke="currentColor" strokeWidth="1.8" />
                        </svg>
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            </div>
          ) : (
            <div className="mx-auto flex max-w-[1120px] scroll-pt-4 flex-col gap-10 px-5 py-8 sm:px-10 [&>article]:scroll-mt-6">
              {thread.map((t) => (
                <Exchange key={t.id} question={t.question} onAnswered={onAnswered} />
              ))}
              <div ref={threadEnd} />
            </div>
          )}
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            ask(draft);
          }}
          className="border-t border-rule px-5 pt-3 pb-3 sm:px-10"
        >
          <div className="mx-auto flex max-w-[1120px] items-end gap-2.5">
            <label htmlFor="question" className="sr-only">
              Your question
            </label>
            <textarea
              id="question"
              ref={input}
              rows={1}
              value={draft}
              maxLength={MAX_CHARS}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  ask(draft);
                }
              }}
              placeholder="Ask about any game…"
              className="max-h-40 min-h-[52px] min-w-0 flex-1 resize-none border border-rule bg-sheet px-4 py-3.5 text-[17px] text-ink [field-sizing:content] placeholder:text-muted focus:outline-2 focus:outline-offset-0 focus:outline-ink"
            />
            <button
              type="submit"
              aria-disabled={!draft.trim()}
              className="flex min-h-[52px] shrink-0 cursor-pointer items-center gap-2 self-stretch bg-ink px-6 font-agate text-[17px] font-bold text-paper hover:bg-ink-soft aria-disabled:cursor-default aria-disabled:hover:bg-ink"
            >
              Ask
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path d="M2 8h11M9 4l4 4-4 4" stroke="currentColor" strokeWidth="2" />
              </svg>
            </button>
          </div>
          <div className="mx-auto mt-2 flex max-w-[1120px] flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
            <p className="m-0 hidden font-agate text-[13px] text-muted sm:block">
              Each question is answered on its own, so name the player, team and season every time.
            </p>
            <AccuracyLine />
          </div>
        </form>
      </main>
      <HowItWorksPanel onOpenChange={setHowOpen} />
    </div>
  );
}
