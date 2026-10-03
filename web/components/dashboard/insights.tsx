"use client";

// The firm-wide views: where every request sits in the workflow, and what the workspace is saving.
import React, { useMemo, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip as RTooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { prettyCategory, type CaseRow, type Lifecycle } from "@/lib/api";
import { Chip } from "./section";
import { LIFECYCLE_LABELS, PRIORITY_DOT, timeAgo } from "./labels";

const BLUE = "#1677ff";
const PIPELINE_COLS: Lifecycle[] = ["new", "awaiting_client", "assigned", "scheduled", "resolved"];

function PageHeader({ title, lede }: { title: string; lede: string }) {
  return (
    <header>
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      <p className="mt-1 text-sm text-muted-foreground">{lede}</p>
    </header>
  );
}

export function PipelineBoard({ cases, loading, onOpen }: { cases: CaseRow[]; loading: boolean; onOpen: (id: string) => void }) {
  const cols = useMemo(() => {
    const m = Object.fromEntries(PIPELINE_COLS.map((c) => [c, [] as CaseRow[]])) as Record<Lifecycle, CaseRow[]>;
    cases.forEach((c) => m[c.lifecycle || "new"].push(c));
    // Within a stage, the most pressing request sits on top.
    PIPELINE_COLS.forEach((c) => m[c].sort((a, b) => (a.priority?.rank ?? 2) - (b.priority?.rank ?? 2) || a.created_at.localeCompare(b.created_at)));
    return m;
  }, [cases]);
  return (
    <div className="flex h-full flex-col p-5 lg:p-8">
      <PageHeader title="Pipeline" lede="Every request, by where it is in the advisor workflow." />
      <div className="mt-6 flex min-h-0 flex-1 gap-3 overflow-x-auto pb-2">
        {PIPELINE_COLS.map((col) => (
          <section key={col} aria-label={LIFECYCLE_LABELS[col]} className="flex w-64 flex-none flex-col rounded-xl bg-muted/60 xl:w-auto xl:flex-1">
            <div className="flex items-center justify-between px-3.5 pb-2 pt-3">
              <h2 className="text-sm font-semibold">{LIFECYCLE_LABELS[col]}</h2>
              <span className="text-xs tabular-nums text-muted-foreground">{loading && !cases.length ? "" : cols[col].length}</span>
            </div>
            <div className="min-h-0 flex-1 space-y-2 overflow-y-auto px-2 pb-2">
              {cols[col].length === 0 && <p className="px-1.5 py-8 text-center text-xs text-muted-foreground">{loading ? "Loading…" : "Nothing at this stage"}</p>}
              {cols[col].map((c) => (
                <button key={c.case_id} onClick={() => onOpen(c.case_id)}
                  className="block w-full rounded-lg border border-border bg-card p-3 text-left shadow-[0_1px_0_rgba(21,32,51,0.04)] outline-none transition-colors hover:border-primary/50 focus-visible:ring-2 focus-visible:ring-primary/40">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-medium">{c.client_display_name}</span>
                    <span className="flex-none text-xs tabular-nums text-muted-foreground">{timeAgo(c.created_at)}</span>
                  </div>
                  <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{c.confirmed_plain_language_request}</p>
                  <div className="mt-2 flex items-center gap-2">
                    {c.priority && col !== "resolved" && <span title={c.priority.reason} className={`h-2 w-2 flex-none rounded-full ${PRIORITY_DOT[c.priority.level]}`} />}
                    {(c.categories || [])[0] && <Chip tone={c.categories?.includes("fraud_or_security") ? "red" : "muted"}>{prettyCategory(c.categories[0])}</Chip>}
                  </div>
                </button>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}

function Tile({ big, label, tone }: { big: string; label: string; tone?: string }) {
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className={`text-3xl font-semibold tracking-tight tabular-nums ${tone || "text-foreground"}`}>{big}</div>
      <p className="mt-2 text-sm text-muted-foreground">{label}</p>
    </div>
  );
}

function median(values: number[]) {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : Math.round((sorted[mid - 1] + sorted[mid]) / 2);
}

const CAPACITY_INPUTS = [
  { key: "requests", label: "Unclear requests per advisor per week" },
  { key: "minutes", label: "Minutes saved per request" },
  { key: "advisors", label: "Advisors" },
  { key: "weeks", label: "Working weeks per year" },
] as const;

// A formula, not a result: every input is editable so nobody has to take our word for the total.
function CapacityModel() {
  const [inputs, setInputs] = useState({ requests: 5, minutes: 10, advisors: 32500, weeks: 50 });
  const hours = Math.round((inputs.requests * inputs.minutes * inputs.advisors * inputs.weeks) / 60);
  return (
    <div className="mt-3 rounded-xl border border-border bg-card p-5">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {CAPACITY_INPUTS.map((f) => (
          <label key={f.key} className="block text-sm text-muted-foreground">
            {f.label}
            <input type="number" min={0} value={inputs[f.key]}
              onChange={(e) => setInputs((v) => ({ ...v, [f.key]: Math.max(0, Number(e.target.value) || 0) }))}
              className="mt-1.5 w-full rounded-lg border border-border bg-background px-3 py-2 text-lg font-medium tabular-nums text-foreground outline-none focus:ring-2 focus:ring-primary/30" />
          </label>
        ))}
      </div>
      <div className="mt-5 border-t border-border pt-4">
        <div className="text-3xl font-semibold tracking-tight tabular-nums text-primary">{hours.toLocaleString()} advisor hours a year</div>
        <p className="mt-2 text-sm text-muted-foreground">
          Requests × minutes × advisors × weeks ÷ 60. The first two inputs are assumptions, not measurements. A pilot would measure them.
        </p>
      </div>
    </div>
  );
}

function CountBars({ title, data }: { title: string; data: { name: string; value: number }[] }) {
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <h3 className="text-sm font-semibold">{title}</h3>
      {data.length === 0 ? <p className="mt-4 text-sm text-muted-foreground">No requests to count yet.</p> : (
        <div className="mt-4" style={{ height: Math.max(120, data.length * 36 + 30) }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} layout="vertical" margin={{ left: 8, right: 20 }}>
              <CartesianGrid horizontal={false} stroke="#e5e7eb" />
              <XAxis type="number" tick={{ fontSize: 11, fill: "#6b7280" }} allowDecimals={false} />
              <YAxis type="category" dataKey="name" width={150} tick={{ fontSize: 12, fill: "#374151" }} tickLine={false} axisLine={false} />
              <RTooltip cursor={{ fill: "rgba(22, 119, 255, 0.06)" }} formatter={(v: any) => [v, "Requests"]} />
              <Bar dataKey="value" fill={BLUE} radius={[0, 4, 4, 0]} barSize={16} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

function Heading({ children }: { children: React.ReactNode }) {
  return <h2 className="mt-10 text-base font-semibold tracking-tight">{children}</h2>;
}

export type Impact = {
  total: number; clarifyPct: number; security: number; assigned: number;
  intakes: { turns: number; seconds_to_confirm: number }[];
  categories: { name: string; value: number }[]; destinations: { name: string; value: number }[];
};

export function ImpactView({ impact }: { impact: Impact }) {
  const { intakes } = impact;
  return (
    <div className="h-full overflow-y-auto p-5 lg:p-8">
      <div className="mx-auto max-w-6xl">
        <PageHeader title="Impact" lede="Live from the request queue, plus a capacity model you can change." />
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Tile big={String(impact.total)} label="Requests in the queue" tone="text-primary" />
          <Tile big={`${impact.clarifyPct}%`} label="Needed clarification before routing" />
          <Tile big={String(impact.security)} label="Flagged as a possible security issue" tone="text-red-600" />
          <Tile big={String(impact.assigned)} label="Assigned to an advisor" tone="text-emerald-600" />
        </div>
        <div className="mt-3 grid items-start gap-3 lg:grid-cols-2">
          <CountBars title="What clients ask for" data={impact.categories} />
          <CountBars title="Where requests are routed" data={impact.destinations} />
        </div>
        <Heading>Measured in this workspace</Heading>
        {intakes.length === 0 ? (
          <p className="mt-3 rounded-xl border border-dashed border-border p-5 text-sm text-muted-foreground">
            No live intakes yet. Send a request from client intake and its turns and time to confirmation appear here.
          </p>
        ) : (
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <Tile big={String(median(intakes.map((i) => i.turns)))} label="Median client turns to a confirmed request" tone="text-primary" />
            <Tile big={`${median(intakes.map((i) => i.seconds_to_confirm))}s`} label="Median time from first message to confirmation" tone="text-primary" />
            <Tile big={String(intakes.length)} label={`Live intake${intakes.length === 1 ? "" : "s"} measured. Seeded demo cases are excluded.`} />
          </div>
        )}
        <Heading>Advisor capacity model</Heading>
        <CapacityModel />
        <Heading>Why it matters at scale</Heading>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Tile big="61.2M" label="Americans are 65+, the clients who struggle most with financial terms." />
          <Tile big="<50%" label="of an advisor's time goes to direct client work today (Kitces)." />
          <Tile big="$2.6T" label="assets & about 32,500 advisors at LPL Financial alone." />
        </div>
      </div>
    </div>
  );
}
