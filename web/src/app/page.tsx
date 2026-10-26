import { Suspense } from "react";
import { AskForm } from "@/components/AskForm";
import { GamesStrip, GamesStripSkeleton } from "@/components/GamesStrip";
import { SiteHeader } from "@/components/SiteHeader";

export default function Home() {
  return (
    <>
      <SiteHeader tone="light" />
      <main className="flex flex-1 flex-col items-center gap-24 px-4 pt-16 pb-16 sm:px-6 sm:pt-24">
        <section className="flex w-full flex-col items-center gap-6 text-center">
          <h1 className="m-0 max-w-[16ch] font-display text-[clamp(44px,8vw,104px)] leading-none font-black tracking-[-0.03em]">
            Ask anything about the NBA. <span className="text-court">See the proof.</span>
          </h1>
          <p className="m-0 max-w-[46ch] text-lg text-muted sm:text-xl">
            Plain-English questions about every game since 2015-16. Each answer shows the query it
            ran and the rows it came from.
          </p>
          <div className="mt-4 w-full max-w-[720px]">
            <AskForm large />
          </div>
        </section>

        <section aria-labelledby="last-night" className="flex w-full max-w-[1120px] flex-col gap-4">
          <h2 id="last-night" className="m-0 font-display text-[26px] font-extrabold">
            Last night&apos;s games
          </h2>
          <Suspense fallback={<GamesStripSkeleton />}>
            <GamesStrip />
          </Suspense>
        </section>
      </main>
    </>
  );
}
