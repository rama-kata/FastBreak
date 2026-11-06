// Past questions and their answers, kept in this browser only, so History can show an
// answer again without asking the model.
import type { AskResult } from "./types";

export type HistoryItem = { question: string; at: number; result: AskResult };

const KEY = "fastbreak.history.v1";
const MAX_ITEMS = 30;
const EMPTY: HistoryItem[] = [];

let items: HistoryItem[] | null = null; // read from storage on first use
const listeners = new Set<() => void>();

function read(): HistoryItem[] {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as HistoryItem[]) : EMPTY;
  } catch {
    return EMPTY;
  }
}

function write(next: HistoryItem[]) {
  items = next;
  try {
    if (next.length) localStorage.setItem(KEY, JSON.stringify(next));
    else localStorage.removeItem(KEY);
  } catch {
    // storage full or blocked: History just won't survive a reload
  }
  listeners.forEach((l) => l());
}

export const history = {
  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
  snapshot: () => (items ??= read()),
  serverSnapshot: () => EMPTY,
  save(item: HistoryItem) {
    const current = history.snapshot();
    if (current[0]?.question === item.question && current[0]?.result.sql === item.result.sql) return;
    write([item, ...current.filter((i) => i.question !== item.question)].slice(0, MAX_ITEMS));
  },
  clear: () => write(EMPTY),
};
