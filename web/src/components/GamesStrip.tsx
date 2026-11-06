import Link from "next/link";
import { getLatestGames } from "@/lib/api";
import { dayAndDate, longMonth } from "@/lib/format";
import type { Game } from "@/lib/types";

// Last night's line scores, set like the agate strip across the top of a sports page.
// The row scrolls sideways and snaps to whole games, so a game is never cut in half.

const strip = "flex snap-x snap-mandatory overflow-x-auto border-b border-rule";

function TeamLine({ name, pts, won }: { name: string; pts: number; won: boolean }) {
  return (
    <div className={`flex items-baseline justify-between gap-3 ${won ? "font-bold text-ink" : "text-ink-soft"}`}>
      <span className="truncate">{name}</span>
      <span>{pts}</span>
    </div>
  );
}

function GameCell({ game, date, day }: { game: Game; date: string; day: string }) {
  const { away, home, top_scorer } = game;
  const awayWon = away.pts > home.pts;
  const matchup = `${away.name} vs ${home.name}`;
  const question = `Who were the top scorers for each team in the ${matchup} game on ${longMonth(date)}?`;
  const youtube = `https://www.youtube.com/results?search_query=${encodeURIComponent(`${matchup} highlights ${longMonth(date)}`)}`;
  return (
    <article className="flex w-1/2 shrink-0 snap-start sm:w-[216px] flex-col gap-1 border-r border-rule px-4 pt-2.5 pb-2 font-agate text-[14px] leading-snug">
      <span className="text-[11px] font-bold tracking-[0.1em] text-spot uppercase">
        {game.overtimes ? `Final · ${game.overtimes > 1 ? `${game.overtimes}OT` : "OT"}` : "Final"}
        <span className="sm:hidden"> · {day}</span>
      </span>
      <TeamLine name={away.name} pts={away.pts} won={awayWon} />
      <TeamLine name={home.name} pts={home.pts} won={!awayWon} />
      {top_scorer && (
        <p className="m-0 truncate text-[13px] text-muted">
          {top_scorer.name}, {top_scorer.pts}
        </p>
      )}
      <div className="mt-0.5 flex gap-3 text-[13px] font-bold">
        <Link
          href={{ pathname: "/", query: { q: question } }}
          scroll={false}
          className="inline-flex min-h-8 items-center underline"
        >
          Ask about it
        </Link>
        <a
          href={youtube}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`Watch ${away.name} at ${home.name} highlights on YouTube (opens a new tab)`}
          className="inline-flex min-h-8 items-center gap-1 underline"
        >
          Highlights
          <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
            <path d="M3 1h6v6M9 1L1 9" stroke="currentColor" strokeWidth="1.5" fill="none" />
          </svg>
        </a>
      </div>
    </article>
  );
}

function DateCell({ children }: { children: React.ReactNode }) {
  return (
    <div className="hidden w-[112px] shrink-0 snap-start flex-col sm:flex justify-center border-r border-rule px-4 font-agate text-[13px] leading-tight">
      {children}
    </div>
  );
}

export async function GamesStrip() {
  const latest = await getLatestGames();
  if (!latest?.date || latest.games.length === 0) {
    return (
      <div className={strip}>
        <p className="m-0 px-4 py-3 font-agate text-[14px] text-muted">Last night&apos;s scores aren&apos;t available right now.</p>
      </div>
    );
  }
  const [day, date] = dayAndDate(latest.date).split(", ");
  return (
    <section aria-label={`Final scores, ${dayAndDate(latest.date)}`} className={strip}>
      <DateCell>
        <span className="font-bold">{day}</span>
        <span>{date}</span>
        <span className="mt-1 text-muted">{latest.games.length} final{latest.games.length === 1 ? "" : "s"}</span>
      </DateCell>
      {latest.games.map((g) => (
        <GameCell key={g.game_id} game={g} date={latest.date!} day={date} />
      ))}
    </section>
  );
}

export function GamesStripSkeleton() {
  return (
    <div className={strip} aria-hidden="true">
      <DateCell>
        <span className="h-3 w-12 bg-rule" />
      </DateCell>
      {Array.from({ length: 6 }, (_, i) => (
        <div key={i} className="flex w-1/2 shrink-0 sm:w-[216px] flex-col gap-2 border-r border-rule px-4 py-3">
          <span className="h-2.5 w-10 bg-rule" />
          <span className="h-3 w-full bg-rule/60" />
          <span className="h-3 w-full bg-rule/60" />
          <span className="h-3 w-24 bg-rule/40" />
        </div>
      ))}
    </div>
  );
}
