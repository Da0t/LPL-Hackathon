"use client";

import React, { useEffect, useMemo, useState, useCallback } from "react";
import Link from "next/link";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip as RTooltip, ResponsiveContainer,
  PieChart, Pie, Cell, CartesianGrid,
} from "recharts";
import {
  Inbox, UserPlus, Flag, ShieldAlert, CheckCircle2, Search, RefreshCw,
  ArrowLeft, MessageSquareQuote, Home, Clock, Hash,
} from "lucide-react";
import { CoherentMark } from "@/components/coherent-logo";
import { Button } from "@/components/ui/button";
import {
  getCases, getCase, getCandidates, assignCase, ApiError, prettyCategory,
  type CaseRow, type Candidate,
} from "@/lib/api";

const BLUE = "#1677ff";
const CHART_COLORS = ["#1677ff", "#60a5fa", "#93c5fd", "#1e40af", "#bfdbfe", "#3b82f6", "#1d4ed8", "#cbd5e1"];

function timeAgo(iso: string): string {
  const t = Date.parse(iso);
  if (isNaN(t)) return "";
  const s = Math.max(0, (Date.now() - t) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

function prettyStatus(s: string): string {
  return (s || "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    submitted: "bg-primary/10 text-primary",
    staff_review: "bg-amber-100 text-amber-700",
    assigned: "bg-emerald-100 text-emerald-700",
  };
  const cls = status?.startsWith("needs_")
    ? "bg-amber-100 text-amber-700"
    : map[status] || "bg-muted text-muted-foreground";
  return <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${cls}`}>{prettyStatus(status)}</span>;
}

function Chip({ children, tone = "muted" }: { children: React.ReactNode; tone?: "muted" | "red" | "amber" }) {
  const tones = {
    muted: "bg-muted text-muted-foreground border-border",
    red: "bg-red-50 text-red-600 border-red-200",
    amber: "bg-amber-50 text-amber-700 border-amber-200",
  };
  return <span className={`rounded-md border px-1.5 py-0.5 text-[11px] ${tones[tone]}`}>{children}</span>;
}

type Filter = "all" | "assign" | "flagged" | "security" | "assigned";

export default function DashboardPage() {
  const [cases, setCases] = useState<CaseRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState("");
  const [view, setView] = useState<"queue" | "impact">("queue");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<any>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [candMeta, setCandMeta] = useState<{ destination?: string; reason?: string }>({});
  const [detailLoading, setDetailLoading] = useState(false);
  const [assigning, setAssigning] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const r = await getCases();
      setCases(r.cases || []);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load the request queue.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const openCase = useCallback(async (id: string) => {
    setSelectedId(id); setDetailLoading(true); setDetail(null); setCandidates([]); setCandMeta({});
    try {
      const [c, cand] = await Promise.all([getCase(id), getCandidates(id).catch(() => ({ candidates: [] }))]);
      setDetail(c);
      setCandidates((cand as any).candidates || []);
      setCandMeta({ destination: (cand as any).destination, reason: (cand as any).reason });
    } catch (e) {
      setDetail({ _error: e instanceof ApiError ? e.message : "Could not load this case." });
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const doAssign = async (advisor_id: string, reason: string) => {
    if (!selectedId) return;
    setAssigning(advisor_id);
    try {
      await assignCase(selectedId, advisor_id, reason || "Assigned by staff.");
      await Promise.all([load(), openCase(selectedId)]);
    } catch (e) {
      alert(e instanceof ApiError ? e.message : "Assignment failed.");
    } finally {
      setAssigning(null);
    }
  };

  const isSecurity = (c: CaseRow) => c.categories?.includes("fraud_or_security");
  const isAssigned = (c: CaseRow) => c.status === "assigned" || c.routing?.assigned_advisor_id;
  const counts = useMemo(() => ({
    all: cases.length,
    assign: cases.filter((c) => c.status === "submitted" && !isAssigned(c) && !isSecurity(c)).length,
    flagged: cases.filter((c) => (c.flags?.length || 0) > 0).length,
    security: cases.filter(isSecurity).length,
    assigned: cases.filter(isAssigned).length,
  }), [cases]);

  const filtered = useMemo(() => {
    let list = cases;
    if (filter === "assign") list = list.filter((c) => c.status === "submitted" && !isAssigned(c) && !isSecurity(c));
    else if (filter === "flagged") list = list.filter((c) => (c.flags?.length || 0) > 0);
    else if (filter === "security") list = list.filter(isSecurity);
    else if (filter === "assigned") list = list.filter(isAssigned);
    const q = search.trim().toLowerCase();
    if (q) list = list.filter((c) =>
      c.client_display_name?.toLowerCase().includes(q) ||
      c.case_id?.toLowerCase().includes(q) ||
      c.confirmed_plain_language_request?.toLowerCase().includes(q));
    return list;
  }, [cases, filter, search]);

  const impact = useMemo(() => {
    const total = cases.length || 1;
    const clarify = cases.filter((c) => c.flags?.includes("client_term_did_not_match_account_type") || c.status?.startsWith("needs_")).length;
    const catCount: Record<string, number> = {};
    const statusCount: Record<string, number> = {};
    const destCount: Record<string, number> = {};
    cases.forEach((c) => {
      (c.categories || []).forEach((cat) => (catCount[cat] = (catCount[cat] || 0) + 1));
      statusCount[c.status] = (statusCount[c.status] || 0) + 1;
      const d = c.routing?.destination || "unrouted";
      destCount[d] = (destCount[d] || 0) + 1;
    });
    return {
      total: cases.length,
      clarifyPct: Math.round((clarify / total) * 100),
      security: cases.filter(isSecurity).length,
      assigned: cases.filter(isAssigned).length,
      categories: Object.entries(catCount).map(([k, v]) => ({ name: prettyCategory(k), value: v })).sort((a, b) => b.value - a.value),
      statuses: Object.entries(statusCount).map(([k, v]) => ({ name: prettyStatus(k), value: v })),
      destinations: Object.entries(destCount).map(([k, v]) => ({ name: prettyStatus(k), value: v })).sort((a, b) => b.value - a.value),
    };
  }, [cases]);

  const navItems: { key: Filter; label: string; icon: any; count: number }[] = [
    { key: "all", label: "All requests", icon: Inbox, count: counts.all },
    { key: "assign", label: "To assign", icon: UserPlus, count: counts.assign },
    { key: "flagged", label: "Flagged", icon: Flag, count: counts.flagged },
    { key: "security", label: "Security", icon: ShieldAlert, count: counts.security },
    { key: "assigned", label: "Assigned", icon: CheckCircle2, count: counts.assigned },
  ];

  return (
    <div className="flex min-h-screen pt-14">
      {/* Sidebar */}
      <aside className="hidden w-60 shrink-0 flex-col border-r border-border bg-muted/30 p-4 md:flex">
        <div className="flex items-center gap-2 px-1">
          <CoherentMark size={26} />
          <div>
            <div className="text-sm font-semibold leading-tight">Coherent</div>
            <div className="text-[11px] text-muted-foreground">Advisor review</div>
          </div>
        </div>
        <nav className="mt-6 space-y-1">
          {navItems.map((it) => (
            <button key={it.key} onClick={() => { setFilter(it.key); setView("queue"); }}
              className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm transition-colors ${
                view === "queue" && filter === it.key ? "bg-primary/10 text-primary" : "text-foreground hover:bg-foreground/5"}`}>
              <span className="flex items-center gap-2"><it.icon className="h-4 w-4" /> {it.label}</span>
              <span className="text-xs text-muted-foreground">{it.count}</span>
            </button>
          ))}
          <button onClick={() => setView("impact")}
            className={`mt-2 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors ${
              view === "impact" ? "bg-primary/10 text-primary" : "text-foreground hover:bg-foreground/5"}`}>
            <RefreshCw className="h-4 w-4" /> Impact
          </button>
        </nav>
        <div className="mt-auto space-y-2 pt-6 text-xs text-muted-foreground">
          <Link href="/" className="flex items-center gap-2 hover:text-foreground"><Home className="h-3.5 w-3.5" /> Home</Link>
          <Link href="/intake" className="flex items-center gap-2 hover:text-foreground"><ArrowLeft className="h-3.5 w-3.5" /> Client intake</Link>
          <p className="pt-2 leading-relaxed">Simulated staff role · synthetic data only.</p>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-hidden">
        {view === "impact" ? (
          <ImpactView impact={impact} />
        ) : (
          <div className="flex h-[calc(100vh-3.5rem)]">
            {/* Queue list */}
            <section className="flex w-full max-w-md shrink-0 flex-col border-r border-border">
              <div className="border-b border-border p-4">
                <h1 className="text-lg font-semibold">Requests</h1>
                <div className="relative mt-3">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search requests"
                    className="w-full rounded-lg border border-border bg-background py-2 pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-primary/30" />
                </div>
              </div>
              <div className="flex-1 overflow-y-auto">
                {loading && <p className="p-4 text-sm text-muted-foreground">Loading queue…</p>}
                {error && <p className="p-4 text-sm text-red-600">{error}</p>}
                {!loading && !error && filtered.length === 0 && <p className="p-4 text-sm text-muted-foreground">No requests here.</p>}
                {filtered.map((c) => (
                  <button key={c.case_id} onClick={() => openCase(c.case_id)}
                    className={`block w-full border-b border-border p-4 text-left transition-colors hover:bg-foreground/[0.03] ${
                      selectedId === c.case_id ? "bg-primary/5" : ""}`}>
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{c.client_display_name}</span>
                      <span className="flex items-center gap-1 text-[11px] text-muted-foreground"><Clock className="h-3 w-3" />{timeAgo(c.created_at)}</span>
                    </div>
                    <div className="mt-0.5 flex items-center gap-1 text-[11px] text-muted-foreground"><Hash className="h-3 w-3" />{c.case_id}</div>
                    <p className="mt-1.5 line-clamp-2 text-sm text-muted-foreground">{c.confirmed_plain_language_request}</p>
                    <div className="mt-2 flex flex-wrap items-center gap-1.5">
                      <StatusBadge status={c.status} />
                      {(c.categories || []).slice(0, 2).map((cat) => (
                        <Chip key={cat} tone={cat === "fraud_or_security" ? "red" : "muted"}>{prettyCategory(cat)}</Chip>
                      ))}
                      {(c.flags || []).length > 0 && <Chip tone={isSecurity(c) ? "red" : "amber"}>⚑ {c.flags.length}</Chip>}
                    </div>
                  </button>
                ))}
              </div>
            </section>

            {/* Detail */}
            <section className="flex-1 overflow-y-auto bg-background">
              {!selectedId && (
                <div className="flex h-full flex-col items-center justify-center text-center text-muted-foreground">
                  <MessageSquareQuote className="h-8 w-8 opacity-40" />
                  <p className="mt-3 text-lg font-medium text-foreground">Select a request</p>
                  <p className="mt-1 max-w-xs text-sm">See the client's words, what they confirmed, and the account facts behind it.</p>
                </div>
              )}
              {selectedId && detailLoading && <p className="p-8 text-sm text-muted-foreground">Loading case…</p>}
              {selectedId && detail && !detailLoading && (
                <CaseDetail detail={detail} candidates={candidates} candMeta={candMeta} assigning={assigning} onAssign={doAssign} />
              )}
            </section>
          </div>
        )}
      </main>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-6">
      <h3 className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">{title}</h3>
      <div className="mt-2">{children}</div>
    </div>
  );
}

function CaseDetail({ detail, candidates, candMeta, assigning, onAssign }: any) {
  if (detail._error) return <p className="p-8 text-sm text-red-600">{detail._error}</p>;
  const security = detail.categories?.includes("fraud_or_security");
  const ac = detail.account_context;
  return (
    <div className="mx-auto max-w-2xl p-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">{detail.client_display_name}</h2>
          <p className="font-mono text-xs text-muted-foreground">{detail.case_id} · {prettyStatus(detail.status)}</p>
        </div>
        <StatusBadge status={detail.status} />
      </div>

      <Section title="Client's original words">
        <blockquote className="rounded-lg border-l-2 border-primary bg-muted/40 p-3 text-sm italic">“{detail.original_words}”</blockquote>
      </Section>

      <Section title="Confirmed request">
        <p className="text-sm">{detail.confirmed_plain_language_request}</p>
      </Section>

      {detail.staff_summary && (
        <Section title="Staff summary">
          <p className="text-sm text-muted-foreground">{detail.staff_summary}</p>
        </Section>
      )}

      {ac && (
        <Section title="Account context · record-backed">
          <div className="rounded-lg border border-border p-4 text-sm">
            <div className="flex flex-wrap gap-x-8 gap-y-1">
              <div><span className="text-muted-foreground">Type: </span>{prettyStatus(ac.account_type || "")}</div>
              <div><span className="text-muted-foreground">Account: </span>{ac.masked_identifier}</div>
              {typeof ac.balance === "number" && <div><span className="text-muted-foreground">Balance: </span>${ac.balance.toLocaleString()} <span className="text-xs text-muted-foreground">as of {ac.balance_as_of}</span></div>}
            </div>
            {ac.account_source_id && <div className="mt-1 text-xs text-muted-foreground">Source: {ac.account_source_id}</div>}
            {(ac.relevant_events || []).length > 0 && (
              <ul className="mt-3 space-y-1 border-t border-border pt-3 text-xs text-muted-foreground">
                {ac.relevant_events.map((e: any, i: number) => (
                  <li key={i}>• {prettyStatus(e.type)} · {e.date} <span className="opacity-60">({e.source_id})</span></li>
                ))}
              </ul>
            )}
          </div>
        </Section>
      )}

      {(detail.conflicts || []).length > 0 && (
        <Section title="Flagged conflicts">
          {detail.conflicts.map((c: any, i: number) => (
            <p key={i} className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">{c.statement} <span className="text-xs opacity-70">({c.source_id})</span></p>
          ))}
        </Section>
      )}

      <div className="mt-6 flex flex-wrap gap-1.5">
        {(detail.categories || []).map((c: string) => <Chip key={c} tone={c === "fraud_or_security" ? "red" : "muted"}>{prettyCategory(c)}</Chip>)}
        {(detail.flags || []).map((f: string) => <Chip key={f} tone={security ? "red" : "amber"}>{f.replace(/_/g, " ")}</Chip>)}
      </div>

      {(detail.unresolved_questions || []).length > 0 && (
        <Section title="Unresolved questions">
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            {detail.unresolved_questions.map((q: string, i: number) => <li key={i}>{q}</li>)}
          </ul>
        </Section>
      )}

      <Section title="Routing">
        <div className="rounded-lg border border-border p-4 text-sm">
          <div><span className="text-muted-foreground">Destination: </span><span className={security ? "font-medium text-red-600" : "font-medium"}>{prettyStatus(detail.routing?.destination || candMeta.destination || "")}</span></div>
          {(detail.routing?.reason || candMeta.reason) && <p className="mt-1 text-xs text-muted-foreground">{detail.routing?.reason || candMeta.reason}</p>}
          {detail.routing?.assigned_advisor_id && <p className="mt-2 text-sm text-emerald-600">✓ Assigned to {detail.routing.assigned_advisor_id}</p>}
        </div>
      </Section>

      <Section title={security ? "Specialist review" : "Recommended advisors"}>
        {security ? (
          <p className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            This request involves a possible security concern. It is routed to <b>security specialist review</b>, not a general advisor.
          </p>
        ) : candidates.length === 0 ? (
          <p className="text-sm text-muted-foreground">No candidate advisors returned.</p>
        ) : (
          <div className="space-y-3">
            {candidates.map((a: Candidate) => (
              <div key={a.advisor_id} className="flex items-start justify-between gap-4 rounded-lg border border-border p-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{a.display_name}</span>
                    <span className="font-mono text-xs text-muted-foreground">{a.advisor_id}</span>
                    {a.available ? <Chip>available</Chip> : <Chip tone="amber">full</Chip>}
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1">{(a.specialties || []).map((s) => <Chip key={s}>{prettyCategory(s)}</Chip>)}</div>
                  <p className="mt-1.5 text-xs text-muted-foreground">{a.reason}</p>
                </div>
                <Button size="sm" disabled={!!assigning || !!detail.routing?.assigned_advisor_id}
                  onClick={() => onAssign(a.advisor_id, a.reason)}>
                  {assigning === a.advisor_id ? "Assigning…" : detail.routing?.assigned_advisor_id ? "Assigned" : "Assign"}
                </Button>
              </div>
            ))}
          </div>
        )}
      </Section>
    </div>
  );
}

function Tile({ big, label, tone }: { big: string; label: string; tone?: string }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5">
      <div className={`text-3xl font-semibold tracking-tight ${tone || "text-foreground"}`}>{big}</div>
      <p className="mt-2 text-sm text-muted-foreground">{label}</p>
    </div>
  );
}

function ImpactView({ impact }: { impact: any }) {
  return (
    <div className="h-[calc(100vh-3.5rem)] overflow-y-auto p-8">
      <h1 className="text-2xl font-semibold">Impact</h1>
      <p className="mt-1 text-sm text-muted-foreground">Live from the request queue · plus illustrative scale figures.</p>

      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Tile big={String(impact.total)} label="Total requests in queue" tone="text-primary" />
        <Tile big={`${impact.clarifyPct}%`} label="Needed clarification before routing" />
        <Tile big={String(impact.security)} label="Security / fraud flagged" tone="text-red-600" />
        <Tile big={String(impact.assigned)} label="Assigned to an advisor" tone="text-emerald-600" />
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-border bg-card p-5">
          <h3 className="text-sm font-medium">Request category mix</h3>
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={impact.categories} layout="vertical" margin={{ left: 20, right: 20 }}>
                <CartesianGrid horizontal={false} stroke="#e5e7eb" />
                <XAxis type="number" tick={{ fontSize: 11, fill: "#6b7280" }} allowDecimals={false} />
                <YAxis type="category" dataKey="name" width={130} tick={{ fontSize: 11, fill: "#374151" }} />
                <RTooltip cursor={{ fill: "rgba(22, 119, 255,0.06)" }} />
                <Bar dataKey="value" fill={BLUE} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="rounded-2xl border border-border bg-card p-5">
          <h3 className="text-sm font-medium">Routing destinations</h3>
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={impact.destinations} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90} label={{ fontSize: 11 }}>
                  {impact.destinations.map((_: any, i: number) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                </Pie>
                <RTooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <h2 className="mt-10 text-sm font-mono uppercase tracking-wider text-muted-foreground">Why it matters , at scale</h2>
      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Tile big="61.2M" label="Americans are 65+ , the clients who struggle most with financial terms." />
        <Tile big="<50%" label="of an advisor's time goes to direct client work today (Kitces)." />
        <Tile big="$2.6T" label="assets & 32,000+ advisors at LPL Financial alone." />
        <Tile big="~$80M/yr" label="illustrative recovered advisor capacity at LPL scale (model, not measured)." tone="text-primary" />
      </div>
    </div>
  );
}
