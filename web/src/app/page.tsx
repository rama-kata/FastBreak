import { Suspense } from "react";
import { ChatApp } from "@/components/ChatApp";
import { Freshness } from "@/components/Freshness";
import { GamesStrip, GamesStripSkeleton } from "@/components/GamesStrip";

export default function Home() {
  return (
    // ChatApp reads ?q= (from "Ask about it" links), which needs a Suspense boundary.
    <Suspense>
      <ChatApp
        games={
          <Suspense fallback={<GamesStripSkeleton />}>
            <GamesStrip />
          </Suspense>
        }
        freshness={
          <Suspense fallback={<span>Checking data…</span>}>
            <Freshness />
          </Suspense>
        }
      />
    </Suspense>
  );
}
