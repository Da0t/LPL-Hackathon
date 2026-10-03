// Portfolio history derived from the client's recorded account events.
// Every activity entry carries balance_after, so the value line is the
// custodian's own record carried forward between events, never an estimate.
import type { Account, Activity } from "@/lib/portal";

export type Point = { date: string; value: number };
export type Range = "1M" | "3M" | "YTD" | "1Y" | "ALL";
export const RANGES: Range[] = ["1M", "3M", "YTD", "1Y", "ALL"];
export const RANGE_LABEL: Record<Range, string> = {
  "1M": "Past month",
  "3M": "Past 3 months",
  YTD: "This year",
  "1Y": "Past year",
  ALL: "All time",
};

const byDate = (a: { date: string }, b: { date: string }) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0);

/** Last recorded value on or before a date; 0 before the account existed. */
export function valueAt(points: Point[], date: string): number {
  let v = 0;
  for (const p of points) {
    if (p.date <= date) v = p.value;
    else break;
  }
  return v;
}

function dedupe(points: Point[]): Point[] {
  const out: Point[] = [];
  for (const p of points) {
    if (out.length && out[out.length - 1].date === p.date) out[out.length - 1] = p;
    else out.push(p);
  }
  return out;
}

export function accountSeries(account: Account, activity: Activity[]): Point[] {
  const events = activity
    .filter((e) => e.account_id === account.account_id && e.balance_after != null)
    .sort(byDate);
  const points: Point[] = [];
  if (account.opened_date && typeof account.opening_value === "number") {
    points.push({ date: account.opened_date, value: account.opening_value });
  } else if (events.length) {
    points.push({ date: events[0].date, value: (events[0].balance_after as number) - (events[0].value_change ?? 0) });
  }
  for (const e of events) points.push({ date: e.date, value: e.balance_after as number });
  const last = points[points.length - 1];
  if (!last || last.date < account.balance_as_of) points.push({ date: account.balance_as_of, value: account.balance });
  return dedupe(points.sort(byDate));
}

export function totalSeries(accounts: Account[], activity: Activity[]): Point[] {
  const per = accounts.map((a) => accountSeries(a, activity));
  const dates = Array.from(new Set(per.flat().map((p) => p.date))).sort();
  return dates.map((date) => ({ date, value: per.reduce((sum, pts) => sum + valueAt(pts, date), 0) }));
}

function shift(asOf: string, months: number): string {
  const d = new Date(asOf + "T00:00:00Z");
  d.setUTCMonth(d.getUTCMonth() - months);
  return d.toISOString().slice(0, 10);
}

/** The part of a series inside a range, starting from the carried value at the range start. */
export function clipSeries(series: Point[], range: Range, asOf: string): Point[] {
  if (!series.length) return [];
  const start =
    range === "1M" ? shift(asOf, 1) : range === "3M" ? shift(asOf, 3) : range === "1Y" ? shift(asOf, 12) : range === "YTD" ? `${asOf.slice(0, 4)}-01-01` : null;
  let out = start && start > series[0].date ? [{ date: start, value: valueAt(series, start) }, ...series.filter((p) => p.date > start)] : [...series];
  const last = out[out.length - 1];
  if (last.date < asOf) out = [...out, { date: asOf, value: last.value }];
  return out;
}

export const shortDate = (iso: string, withYear = false) =>
  new Date(iso + "T00:00:00").toLocaleDateString("en-US", withYear ? { month: "short", day: "numeric", year: "numeric" } : { month: "short", day: "numeric" });
