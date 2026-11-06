// The accuracy line under the question box, and the panel it opens: how an answer is
// made, how often it's right on the test set, and what the checks can't catch.

const REPO = "https://github.com/rama-kata/FastBreak";

const h3 = "m-0 font-agate text-[13px] font-bold tracking-[0.08em] uppercase";

export function AccuracyLine() {
  return (
    <p className="m-0 font-agate text-[13px] text-muted">
      Right on <strong className="text-ink">36 of 50</strong> test questions, so check the box score.{" "}
      <button
        type="button"
        popoverTarget="how-it-works"
        className="min-h-8 cursor-pointer font-bold text-ink underline underline-offset-3 hover:decoration-2"
      >
        How it works
      </button>
    </p>
  );
}

/** A sheet on the right. `onOpenChange` lets the page make room for it on wide screens. */
export function HowItWorksPanel({ onOpenChange }: { onOpenChange?: (open: boolean) => void }) {
  return (
    <div
      id="how-it-works"
      popover="auto"
      onToggle={(e) => onOpenChange?.((e.nativeEvent as ToggleEvent).newState === "open")}
      aria-labelledby="how-heading"
      className="fixed inset-y-0 right-0 left-auto m-0 h-dvh max-h-none w-[min(460px,100vw)] overflow-y-auto border-0 border-l border-rule bg-paper p-0 text-ink backdrop:bg-transparent"
    >
      <div className="flex items-start justify-between gap-4 border-b-4 border-double border-ink px-6 pt-5 pb-3">
        <h2 id="how-heading" className="m-0 text-[30px] leading-none font-black tracking-[-0.025em]">
          How FastBreak answers
        </h2>
        <button
          type="button"
          popoverTarget="how-it-works"
          popoverTargetAction="hide"
          className="flex min-h-10 cursor-pointer items-center gap-1.5 px-2 font-agate text-[14px] font-bold underline-offset-3 hover:underline"
        >
          Close
          <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
            <path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" strokeWidth="1.6" />
          </svg>
        </button>
      </div>

      <div className="flex flex-col gap-6 px-6 pt-5 pb-6 text-[15px] leading-relaxed text-ink-soft">
        <section className="flex flex-col gap-2">
          <h3 className={h3}>Every answer, in four steps</h3>
          <ol className="m-0 flex list-none flex-col gap-2 p-0 [counter-reset:step]">
            {[
              "A language model (qwen3:14b, running on a home PC) writes a read-only SQL query for your question.",
              "The query runs on a database of about 14,250 NBA games since 2015-16, loaded from NBA.com box scores every night.",
              "The model writes the answer from the rows the query returned.",
              "Every number in the answer is checked against those rows. If one isn't there, the answer is held back and you see the rows instead.",
            ].map((s) => (
              <li key={s} className="grid grid-cols-[1.5rem_1fr] gap-2 [counter-increment:step] before:font-agate before:font-bold before:text-ink before:content-[counter(step)]">
                {s}
              </li>
            ))}
          </ol>
        </section>

        <section className="flex flex-col gap-2">
          <h3 className={h3}>How often it&apos;s right</h3>
          <p className="m-0">
            It&apos;s scored on 50 hand-written questions with known answers. A question counts only when the
            query returns the right rows.
          </p>
          <table className="w-full border-collapse font-agate text-[14px]">
            <thead>
              <tr className="border-b border-rule text-left">
                <th scope="col" className="py-1.5 font-bold">Mode</th>
                <th scope="col" className="py-1.5 text-right font-bold">Right</th>
                <th scope="col" className="py-1.5 text-right font-bold">Typical answer</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-rule font-bold text-ink">
                <td className="py-1.5">Quick (this site)</td>
                <td className="py-1.5 text-right">36 of 50</td>
                <td className="py-1.5 text-right">6 s</td>
              </tr>
              <tr className="border-b border-rule">
                <td className="py-1.5">Thinking on hard questions</td>
                <td className="py-1.5 text-right">40 of 50</td>
                <td className="py-1.5 text-right">11 s, slow ones 2 min</td>
              </tr>
              <tr className="border-b border-rule">
                <td className="py-1.5">Thinking on every question</td>
                <td className="py-1.5 text-right">44 of 50</td>
                <td className="py-1.5 text-right">55 s</td>
              </tr>
            </tbody>
          </table>
          <p className="m-0 text-[14px] text-muted">
            50 questions is a small test: 36 of 50 means the true rate is somewhere between 58% and 82%.
          </p>
        </section>

        <section className="flex flex-col gap-2">
          <h3 className={h3}>What the check can&apos;t catch</h3>
          <p className="m-0">
            The check proves every number came from the rows. It can&apos;t tell when the query answered a
            different question: asked for the most points in a single game, it once added up a whole
            season. That&apos;s why the box score and the query sit under every answer.
          </p>
          <p className="m-0">
            Each question is answered on its own, with no memory of the last one, so name the player, team
            and season every time.
          </p>
        </section>

        <p className="m-0 border-t border-rule pt-3 font-agate text-[14px]">
          <a href={REPO} target="_blank" rel="noopener noreferrer" className="font-bold">
            The test questions, every run&apos;s results and the code, on GitHub
          </a>
        </p>
      </div>
    </div>
  );
}
