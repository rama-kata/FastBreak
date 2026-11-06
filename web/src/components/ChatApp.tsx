"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { seedRun } from "@/lib/ask-store";
import { history as historyStore, type HistoryItem } from "@/lib/history";
import type { AskResult } from "@/lib/types";
import { Exchange } from "./Answer";

const MAX_CHARS = 300; // the API's limit

const SUGGESTIONS = [
  "Who made the most three-pointers from 2015-16 to 2025-26?",
  "What was the Warriors' regular season record in 2015-16?",
  "How many points did Klay Thompson score on December 5, 2016?",
];

function Wordmark({ size }: { size: "lg" | "sm" }) {
  return (
    <span
      className={`font-display font-black tracking-tight italic ${size === "lg" ? "text-[34px]" : "text-[22px]"}`}
    >
      <span className="text-cream">Fast</span>
      <span className="text-sun">Break</span>
    </span>
  );
}

function HistoryList({
  items,
  onPick,
  onClear,
}: {
  items: HistoryItem[];
  onPick: (item: HistoryItem) => void;
  onClear: () => void;
}) {
  return (
    <nav aria-labelledby="history-heading" className="flex min-h-0 flex-1 flex-col gap-2">
      <div className="flex items-center justify-between px-1">
        <h2 id="history-heading" className="m-0 text-xs font-bold tracking-[0.08em] text-[#9aa6b8] uppercase">
          History
        </h2>
        {items.length > 0 && (
          <button
            type="button"
            onClick={onClear}
            className="cursor-pointer rounded px-1.5 py-1 text-xs text-[#9aa6b8] hover:text-cream"
          >
            Clear
          </button>
        )}
      </div>
      {items.length === 0 ? (
        <p className="m-0 px-1 text-sm text-[#9aa6b8]">Questions you ask show up here, kept in this browser.</p>
      ) : (
        <ul className="m-0 flex list-none flex-col gap-0.5 overflow-y-auto p-0">
          {items.map((item) => (
            <li key={item.question}>
              <button
                type="button"
                onClick={() => onPick(item)}
                className="w-full cursor-pointer truncate rounded-lg px-3 py-2.5 text-left text-sm text-[#d5dbe5] hover:bg-white/10 hover:text-white"
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
  const nextId = useRef(1);
  const bottom = useRef<HTMLDivElement>(null);
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

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
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

  const sidebar = (
    <>
      <button type="button" onClick={newChat} className="flex flex-col items-center gap-1 rounded-xl p-1 hover:bg-white/5" aria-label="FastBreak, start a new chat">
        {/* eslint-disable-next-line @next/next/no-img-element -- static brand art */}
        <img src="/mascot.png" alt="" width={172} height={128} className="h-auto w-[172px]" />
        <Wordmark size="lg" />
      </button>
      <button
        type="button"
        onClick={newChat}
        className="flex min-h-11 cursor-pointer items-center gap-2.5 rounded-xl bg-white/10 px-4 font-semibold text-cream hover:bg-white/15"
      >
        <svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true">
          <path d="M10 4v12M4 10h12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
        New chat
      </button>
      <HistoryList items={history} onPick={openFromHistory} onClear={historyStore.clear} />
      <div className="flex flex-col gap-2 border-t border-white/10 pt-4 text-sm text-[#c2cad6]">
        <p className="m-0 font-display text-base font-bold text-cream">Ask anything. See the proof.</p>
        {freshness}
      </div>
    </>
  );

  return (
    <div className="flex h-dvh flex-col bg-paper md:flex-row">
      {/* Phone: a top bar, with History in a drawer */}
      <header className="flex items-center justify-between gap-3 bg-night px-4 py-2.5 md:hidden">
        <button type="button" onClick={newChat} className="flex items-center gap-2" aria-label="FastBreak, start a new chat">
          {/* eslint-disable-next-line @next/next/no-img-element -- static brand art */}
          <img src="/avatar.png" alt="" width={36} height={36} className="size-9 rounded-full" />
          <Wordmark size="sm" />
        </button>
        <button
          type="button"
          onClick={() => setMenuOpen((o) => !o)}
          aria-expanded={menuOpen}
          aria-controls="phone-menu"
          className="flex min-h-11 cursor-pointer items-center rounded-lg px-3 text-sm font-semibold text-cream hover:bg-white/10"
        >
          {menuOpen ? "Close" : "History"}
        </button>
      </header>
      {menuOpen && (
        <div id="phone-menu" className="flex max-h-[70dvh] flex-col gap-5 overflow-y-auto bg-night px-4 pt-2 pb-5 md:hidden">
          {sidebar}
        </div>
      )}

      <aside className="hidden w-[280px] shrink-0 flex-col gap-5 overflow-y-auto bg-night px-4 py-6 md:flex">
        {sidebar}
      </aside>

      <main className="flex min-h-0 min-w-0 flex-1 flex-col">
        <div className="min-h-0 flex-1 overflow-y-auto">
          {thread.length === 0 ? (
            <div className="mx-auto flex max-w-[1040px] flex-col gap-14 px-4 pt-12 pb-10 sm:px-8 sm:pt-20">
              <section className="flex flex-col items-center gap-5 text-center">
                <h1 className="m-0 max-w-[18ch] font-display text-[clamp(38px,5.2vw,68px)] leading-none font-black tracking-[-0.03em]">
                  Ask anything about the NBA. <span className="text-court">See the proof.</span>
                </h1>
                <p className="m-0 max-w-[46ch] text-lg text-muted">
                  Plain-English questions about every game since 2015-16. Each answer shows the query it
                  ran and the rows it came from.
                </p>
                <ul className="m-0 flex max-w-[760px] list-none flex-wrap justify-center gap-2 p-0">
                  {SUGGESTIONS.map((s) => (
                    <li key={s}>
                      <button
                        type="button"
                        onClick={() => ask(s)}
                        className="min-h-11 cursor-pointer rounded-full border border-line-strong bg-white px-4 py-2 text-sm text-ink hover:bg-chalk"
                      >
                        {s}
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
              <section aria-labelledby="last-night" className="flex flex-col gap-4">
                <h2 id="last-night" className="m-0 font-display text-2xl font-extrabold">
                  Last night&apos;s games
                </h2>
                {games}
              </section>
            </div>
          ) : (
            <div className="mx-auto flex max-w-[860px] flex-col gap-8 px-4 py-8 sm:px-8">
              {thread.map((t) => (
                <Exchange key={t.id} question={t.question} onAnswered={onAnswered} />
              ))}
              <div ref={bottom} />
            </div>
          )}
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            ask(draft);
          }}
          className="border-t border-line bg-paper px-4 py-3 sm:px-8 sm:py-4"
        >
          <div className="mx-auto flex max-w-[860px] items-end gap-2.5">
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
              placeholder="Ask me anything about the NBA since 2015-16…"
              className="max-h-40 min-h-[52px] min-w-0 flex-1 resize-none rounded-2xl border-[1.5px] border-line-strong bg-white px-5 py-3.5 text-base text-ink [field-sizing:content] placeholder:text-muted focus:border-navy focus:outline-none"
            />
            <button
              type="submit"
              aria-label="Ask"
              disabled={!draft.trim()}
              className="flex size-[52px] shrink-0 cursor-pointer items-center justify-center rounded-full bg-sun text-ink hover:brightness-95 disabled:cursor-default disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-navy"
            >
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M12 19V5M5.5 11.5L12 5l6.5 6.5" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>
          <p className="mx-auto mt-2 mb-0 max-w-[860px] text-center text-xs text-muted">
            Each question is answered on its own, so name the player, team and season every time.
          </p>
        </form>
      </main>
    </div>
  );
}
