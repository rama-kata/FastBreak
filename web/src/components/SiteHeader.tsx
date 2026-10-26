import Link from "next/link";
import { Suspense } from "react";
import { getStatus } from "@/lib/api";
import { shortDate } from "@/lib/format";
import { Logo } from "./Logo";

async function Freshness({ dark }: { dark: boolean }) {
  const status = await getStatus();
  const online = Boolean(status?.data_through);
  return (
    <span className={`flex items-center gap-2 text-sm ${dark ? "text-line-strong" : "text-muted"}`}>
      <span
        aria-hidden="true"
        className={`size-2 rounded-full ${online ? (dark ? "bg-[#4ade80]" : "bg-court") : "bg-line-strong"}`}
      />
      {online ? `Data through ${shortDate(status!.data_through!)}` : "Data server offline"}
    </span>
  );
}

export function SiteHeader({ tone }: { tone: "light" | "dark" }) {
  const dark = tone === "dark";
  return (
    <header className={dark ? "bg-navy text-white" : ""}>
      <div className="mx-auto flex max-w-[1120px] flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6">
        <Link
          href="/"
          className={`flex items-center gap-2.5 no-underline ${dark ? "text-white hover:text-white" : "text-ink hover:text-ink"}`}
        >
          <Logo color={dark ? "#f2c94c" : "#13294b"} />
          <span className="font-display text-[22px] font-extrabold tracking-tight">FastBreak</span>
        </Link>
        <Suspense fallback={<span className="text-sm opacity-0">Checking data…</span>}>
          <Freshness dark={dark} />
        </Suspense>
      </div>
    </header>
  );
}
