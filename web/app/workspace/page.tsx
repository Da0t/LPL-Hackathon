"use client";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, MessageCircleQuestion } from "lucide-react";
import { useClient } from "@/components/portal/shell";
import PortfolioChart, { Spark } from "@/components/portal/portfolio-chart";
import { money, accountTypes, title } from "@/lib/portal";
import { getMyRequests, type MyRequest, type Lifecycle } from "@/lib/api";
import { accountSeries, clipSeries, totalSeries, RANGES, RANGE_LABEL, shortDate, type Point, type Range } from "@/lib/portfolio";

const UP = "#00C805";
const DOWN = "#FF5000";
const UP_TEXT = "#00a650";

const STATUS: Record<Lifecycle, string> = {
  awaiting_client: "Needs your answer",
  new: "Received",
  assigned: "With an advisor",
  scheduled: "Meeting plan recorded",
  resolved: "Done",
};

function Change({ from, to, period, size = "lg" }: { from: number; to: number; period: string; size?: "lg" | "sm" }) {
  const diff = to - from;
  const pct = from ? (diff / from) * 100 : 0;
  const up = diff >= 0;
  const color = up ? UP_TEXT : DOWN;
  return (
    <span className={`ov-change ${size}`}>
      <span style={{ color }}>
        {up ? "+" : "−"}
        {money(Math.abs(diff))} ({up ? "+" : "−"}
        {Math.abs(pct).toFixed(2)}%)
      </span>
      {period && <span className="period">{period}</span>}
    </span>
  );
}

export default function Overview() {
  const { client, awaiting } = useClient();
  const [range, setRange] = useState<Range>("1Y");
  const [hover, setHover] = useState<Point | null>(null);
  const [requests, setRequests] = useState<MyRequest[] | null>(null);

  useEffect(() => {
    getMyRequests(client.client_id)
      .then((r) => setRequests(r.requests))
      .catch(() => setRequests([]));
  }, [client.client_id]);

  const total = client.accounts.reduce((n, a) => n + a.balance, 0);
  const cash = client.accounts.reduce((n, a) => n + a.cash_balance, 0);

  const series = useMemo(() => clipSeries(totalSeries(client.accounts, client.activity), range, client.as_of), [client, range]);
  const perAccount = useMemo(
    () => Object.fromEntries(client.accounts.map((a) => [a.account_id, clipSeries(accountSeries(a, client.activity), range, client.as_of)])),
    [client, range],
  );

  const first = series[0]?.value ?? total;
  const shown = hover ? hover.value : total;
  const up = shown - first >= 0;
  const accent = up ? UP : DOWN;

  const recent = [...client.activity].sort((a, b) => (a.date < b.date ? 1 : -1)).slice(0, 6);
  const label = (id: string) => client.accounts.find((a) => a.account_id === id)?.familiar_label ?? "";

  return (
    <div className="ov" style={{ "--ov-accent": accent } as React.CSSProperties}>
      <div className="ov-main">
        {awaiting > 0 && (
          <Link className="answer-banner" href="/workspace/requests">
            <MessageCircleQuestion size={22} />
            <span>
              <strong>
                {awaiting === 1 ? "Your advisor has a question about your request." : `Your advisor has questions about ${awaiting} of your requests.`}
              </strong>
              <small>Your request waits until you answer.</small>
            </span>
            <b>
              Answer now <ArrowRight size={16} />
            </b>
          </Link>
        )}

        <h1 className="ov-value" aria-live="polite">
          {money(shown)}
        </h1>
        <Change from={first} to={shown} period={hover ? shortDate(hover.date, true) : RANGE_LABEL[range]} />

        <PortfolioChart points={series} accent={accent} onHover={setHover} />

        <div className="ov-ranges" role="tablist" aria-label="Time range">
          {RANGES.map((r) => (
            <button key={r} type="button" role="tab" aria-selected={r === range} onClick={() => setRange(r)}>
              {r}
            </button>
          ))}
        </div>

        <div className="ov-row">
          <span>
            Recorded cash balance
            <small>Included in the total. Not an amount approved to withdraw.</small>
          </span>
          <b>{money(cash)}</b>
        </div>

        <section className="ov-section">
          <h2>
            Accounts <Link href="/workspace/finances">See all</Link>
          </h2>
          {client.accounts.map((a) => {
            const pts = perAccount[a.account_id];
            const start = pts[0]?.value ?? a.balance;
            const rowAccent = a.balance - start >= 0 ? UP : DOWN;
            return (
              <Link href={"/workspace/finances?account=" + a.account_id} className="ov-item" key={a.account_id}>
                <span>
                  <strong>{a.familiar_label}</strong>
                  <small>
                    {accountTypes[a.account_type] || title(a.account_type)} · {a.masked_identifier}
                  </small>
                </span>
                <Spark points={pts} accent={rowAccent} />
                <span className="amt">
                  <b>{money(a.balance)}</b>
                  <Change from={start} to={a.balance} period="" size="sm" />
                </span>
              </Link>
            );
          })}
        </section>

        <section className="ov-section">
          <h2>
            Recent activity <Link href="/workspace/finances">See history</Link>
          </h2>
          {recent.map((e) => {
            const vc = e.value_change ?? 0;
            return (
              <div className="ov-item two" key={e.event_id}>
                <span>
                  <strong>{e.description}</strong>
                  <small>
                    {label(e.account_id)} · {shortDate(e.date, true)}
                  </small>
                </span>
                <span className="amt">
                  <b style={{ color: vc > 0 ? UP_TEXT : undefined }}>
                    {vc > 0 ? "+" : vc < 0 ? "−" : ""}
                    {vc === 0 && e.amount === 0 ? "" : money(Math.abs(e.amount))}
                  </b>
                  <span>{title(e.type)}</span>
                </span>
              </div>
            );
          })}
        </section>
      </div>

      <aside className="ov-side">
        <section className="ov-section first">
          <h2>
            Requests <Link href="/workspace/requests/new">New request</Link>
          </h2>
          {requests === null ? (
            <p className="ov-empty">Loading…</p>
          ) : requests.length === 0 ? (
            <p className="ov-empty">No requests yet.</p>
          ) : (
            requests.slice(0, 4).map((r) => (
              <Link href="/workspace/requests" className="ov-req" key={r.case_id}>
                <strong>{r.request}</strong>
                <small>
                  <em className={r.lifecycle === "awaiting_client" ? "attention" : ""}>{STATUS[r.lifecycle] ?? "Sent"}</em>
                  {shortDate(r.created_at.slice(0, 10), true)}
                </small>
              </Link>
            ))
          )}
        </section>

        <section className="ov-ask">
          <h3>Something on your mind?</h3>
          <p>Say it in your own words. We bring the relevant account details together and get it to the right advisor.</p>
          <Link className="portal-primary" href="/workspace/requests/new">
            Start a request <ArrowRight size={18} />
          </Link>
        </section>
      </aside>
    </div>
  );
}
