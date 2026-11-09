// Format date-only values in UTC so a US timezone cannot move them back a day.
export function displayMonth(value: string) {
  return new Intl.DateTimeFormat("en-US", {month: "short", year: "numeric", timeZone: "UTC"})
    .format(new Date(`${value}-01T12:00:00Z`));
}
export function displayDate(value: string) {
  return new Intl.DateTimeFormat("en-US", {month: "short", day: "numeric", year: "numeric", timeZone: "UTC"})
    .format(new Date(`${value}T12:00:00Z`));
}
export function shiftMonth(month: string, step: number) {
  const [y, m] = month.split("-").map(Number);
  const date = new Date(Date.UTC(y, m - 1 + step, 1));
  return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}`;
}
