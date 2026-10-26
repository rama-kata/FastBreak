export type Team = { abbreviation: string; name: string; pts: number };

export type Game = {
  game_id: string;
  overtimes: number;
  away: Team;
  home: Team;
  top_scorer: { name: string; team: string; pts: number } | null;
};

export type LatestGames = { date: string | null; games: Game[] };

export type Status = { data_through: string | null; games: number };

export type Cell = string | number | null;

/** The final `result` event from POST /api/ask. */
export type AskResult = {
  question: string;
  sql: string;
  columns: string[];
  rows: Cell[][];
  truncated: boolean;
  answer: string | null;
  draft_answer: string | null;
  ungrounded: number[];
  error: string | null;
  sql_attempts: number;
  seconds: number;
  model: string;
  blocked: boolean;
  number_spans: { start: number; end: number; in_rows: boolean; grounded: boolean }[];
};
