const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

/** "2026-10-24" -> "Oct 24, 2026". Parsed by hand so server and browser agree. */
export function shortDate(iso: string) {
  const [y, m, d] = iso.split("-").map(Number);
  return `${MONTHS[m - 1]} ${d}, ${y}`;
}

/** "2026-10-24" -> "Saturday, Oct 24". */
export function dayAndDate(iso: string) {
  const [y, m, d] = iso.split("-").map(Number);
  const day = DAYS[new Date(Date.UTC(y, m - 1, d)).getUTCDay()];
  return `${day}, ${MONTHS[m - 1]} ${d}`;
}

export function longMonth(iso: string) {
  const [y, m, d] = iso.split("-").map(Number);
  const names = ["January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December"];
  return `${names[m - 1]} ${d} ${y}`;
}
