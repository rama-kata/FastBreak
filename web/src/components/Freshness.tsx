import { getStatus } from "@/lib/api";
import { shortDate } from "@/lib/format";

export async function Freshness() {
  const status = await getStatus();
  const online = Boolean(status?.data_through);
  return (
    <span className="flex items-center gap-2">
      <span aria-hidden="true" className={`size-2 shrink-0 rounded-full ${online ? "bg-ink" : "border border-spot"}`} />
      {online
        ? `Data through ${shortDate(status!.data_through!)} · ${status!.games.toLocaleString("en-US")} games`
        : "Data server offline: answers are paused"}
    </span>
  );
}
