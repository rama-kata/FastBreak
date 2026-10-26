import Link from "next/link";
import { getLatestGames } from "@/lib/api";
import { dayAndDate, longMonth } from "@/lib/format";
import type { Game } from "@/lib/types";

function TeamLine({ name, pts, won }: { name: string; pts: number; won: boolean }) {
  return (
    <div className={`flex items-center justify-between text-lg ${won ? "font-bold text-ink" : "text-muted"}`}>
      <span>{name}</span>
      <span className="font-mono">{pts}</span>
    </div>
  );
}

function GameCard({ game, date }: { game: Game; date: string }) {
  const { away, home, top_scorer } = game;
  const awayWon = away.pts > home.pts;
  const matchup = `${away.name} vs ${home.name}`;
  const question = `Who were the top scorers for each team in the ${matchup} game on ${longMonth(date)}?`;
  const youtube = `https://www.youtube.com/results?search_query=${encodeURIComponent(`${matchup} highlights ${longMonth(date)}`)}`;
  return (
    <article className="flex flex-col gap-2.5 rounded-xl border border-line bg-white px-[18px] py-4">
      <span className="text-xs font-bold uppercase tracking-[0.06em] text-muted">
        {game.overtimes ? `Final · ${game.overtimes > 1 ? `${game.overtimes}OT` : "OT"}` : "Final"}
      </span>
      <div className="flex flex-col gap-1">
        <TeamLine name={away.name} pts={away.pts} won={awayWon} />
        <TeamLine name={home.name} pts={home.pts} won={!awayWon} />
      </div>
      {top_scorer && (
        <p className="m-0 border-t border-line pt-2.5 text-sm text-[#334155]">
          Top scorer: <strong>{top_scorer.name}</strong>, {top_scorer.pts} pts
        </p>
      )}
      <div className="flex gap-2">
        <Link
          href={{ pathname: "/", query: { q: question } }}
          scroll={false}
          className="flex min-h-11 flex-1 items-center justify-center rounded-lg bg-mist text-sm font-semibold text-ink no-underline hover:text-ink hover:brightness-95"
        >
          Ask about it
        </Link>
        <a
          href={youtube}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`Watch ${away.name} at ${home.name} highlights on YouTube (opens a new tab)`}
          className="flex min-h-11 flex-1 items-center justify-center gap-1.5 rounded-lg border border-line-strong text-sm font-semibold text-ink no-underline hover:bg-chalk hover:text-ink"
        >
          <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
            <path d="M5 3.5v9l7-4.5-7-4.5z" fill="currentColor" />
          </svg>
          Highlights
        </a>
      </div>
    </article>
  );
}

export async function GamesStrip() {
  const latest = await getLatestGames();
  if (!latest?.date || latest.games.length === 0) {
    return <p className="m-0 text-muted">Scores aren&apos;t available right now.</p>;
  }
  return (
    <>
      <p className="m-0 text-sm text-muted">{dayAndDate(latest.date)} · final scores from FastBreak&apos;s data</p>
      <div className="grid grid-cols-[repeat(auto-fill,minmax(250px,1fr))] gap-3.5">
        {latest.games.map((g) => (
          <GameCard key={g.game_id} game={g} date={latest.date!} />
        ))}
      </div>
    </>
  );
}

export function GamesStripSkeleton() {
  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(250px,1fr))] gap-3.5" aria-hidden="true">
      {Array.from({ length: 8 }, (_, i) => (
        <div key={i} className="h-[214px] rounded-xl border border-line bg-white/60" />
      ))}
    </div>
  );
}
