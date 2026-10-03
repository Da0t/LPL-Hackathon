"use client";

import React, { useEffect, useMemo, useState, useCallback } from "react";
import Link from "next/link";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip as RTooltip, ResponsiveContainer,
  PieChart, Pie, Cell, CartesianGrid,
} from "recharts";
import {
  Inbox, UserPlus, Flag, ShieldAlert, CheckCircle2, Search, RefreshCw,
  ArrowLeft, MessageSquareQuote, Home, Columns3,
} from "lucide-react";
import {
  getCases, getCase, getCandidates, assignCase, getBrief, getPlan, caseAction, getClientSnapshot, health,
  ApiError, prettyCategory, type CaseRow, type Candidate, type Brief, type ActionPlan, type AdvisorAction,
  type ClientSnapshot, type Lifecycle, type SentCompliance,
} from "@/lib/api";
import { Chip } from "@/components/dashboard/section";
import { CaseDetail, type CaseTab } from "@/components/dashboard/case-detail";
import { LIFECYCLE_LABELS, PRIORITY_DOT, PRIORITY_TEXT, sentence, statusLabel, timeAgo } from "@/components/dashboard/labels";

const BLUE = "#1677ff";
const CHART_COLORS = ["#1677ff", "#60a5fa", "#93c5fd", "#1e40af", "#bfdbfe", "#3b82f6", "#1d4ed8", "#cbd5e1"];

const PIPELINE_COLS: Lifecycle[] = ["new", "awaiting_client", "assigned", "scheduled", "resolved"];
const CASE_TABS: CaseTab[] = ["overview", "plan", "client", "assign", "compliance"];

type Filter = "all" | "assign" | "flagged" | "security" | "assigned";
type Sort = "priority" | "newest";

export default function DashboardPage() {
  const [cases, setCases] = useState<CaseRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [sort, setSort] = useState<Sort>("priority");
  const [search, setSearch] = useState("");
  const [view, setView] = useState<"queue" | "pipeline" | "impact">("queue");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [initialTab, setInitialTab] = useState<CaseTab | undefined>(undefined);
  const [detail, setDetail] = useState<any>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [candMeta, setCandMeta] = useState<{ destination?: string; reason?: string }>({});
  const [snapshot, setSnapshot] = useState<ClientSnapshot | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [assigning, setAssigning] = useState<string | null>(null);
  const [brief, setBrief] = useState<Brief | null>(null);
  const [briefLoading, setBriefLoading] = useState(false);
  const [actionBusy, setActionBusy] = useState(false);
  const [plan, setPlan] = useState<ActionPlan | null>(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [planStage, setPlanStage] = useState(0);
  const [actionError, setActionError] = useState<string | null>(null);
  const [hc, setHc] = useState<any>(null);

  const load = useCallback(async (quiet = false) => {
    if (!quiet) { setLoading(true); setError(null); }
    try { setCases((await getCases()).cases || []); if (quiet) setError(null); }
    catch (e) { if (!quiet) setError(e instanceof ApiError ? e.message : "Could not load the request queue."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);
  // New requests and client replies arrive from elsewhere, so keep the queue current while the tab is visible.
  useEffect(() => {
    const tick = () => { if (document.visibilityState === "visible") load(true); };
    const timer = setInterval(tick, 15000);
    document.addEventListener("visibilitychange", tick);
    return () => { clearInterval(timer); document.removeEventListener("visibilitychange", tick); };
  }, [load]);
  useEffect(() => { health().then(setHc).catch(() => setHc(null)); }, []);

  const loadBrief = useCallback(async (id: string, refresh = false) => {
    setBrief(null); setBriefLoading(true);
    try { setBrief(await getBrief(id, refresh)); } catch { setBrief(null); } finally { setBriefLoading(false); }
  }, []);

  const loadPlan = useCallback(async (id: string) => {
    setPlan(null); setPlanLoading(true); setPlanStage(0);
    const timers = [1, 2, 3, 4].map((i) => setTimeout(() => setPlanStage((s) => Math.max(s, i)), i * 650));
    try { setPlan(await getPlan(id)); } catch { setPlan(null); }
    finally { timers.forEach(clearTimeout); setPlanStage(5); setPlanLoading(false); }
  }, []);

  // Reloads the case without touching the brief, so acting on a case does not re-run the briefing agent.
  const refreshCase = useCallback(async (id: string, showLoading: boolean) => {
    if (showLoading) { setDetailLoading(true); setDetail(null); setCandidates([]); setCandMeta({}); setSnapshot(null); }
    try {
      const [c, cand, snap] = await Promise.all([
        getCase(id), getCandidates(id).catch(() => ({ candidates: [] })), getClientSnapshot(id).catch(() => null),
      ]);
      setDetail(c);
      setCandidates((cand as any).candidates || []);
      setCandMeta({ destination: (cand as any).destination, reason: (cand as any).reason });
      setSnapshot(snap);
    } catch (e) {
      setDetail({ _error: e instanceof ApiError ? e.message : "Could not load this request." });
    } finally { setDetailLoading(false); }
  }, []);

  const openCase = useCallback((id: string, tab?: CaseTab) => {
    setSelectedId(id); setInitialTab(tab); setActionError(null); setView("queue");
    window.history.replaceState(null, "", `?case=${encodeURIComponent(id)}`);
    setBrief(null); loadPlan(id);  // the prepared action leads; the prep brief loads when its tab is opened
    refreshCase(id, true);
  }, [loadPlan, refreshCase]);

  // A link to /dashboard?case=CASE-1042&tab=plan opens that request on that tab.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const id = params.get("case");
    const tab = params.get("tab") as CaseTab | null;
    if (id) openCase(id, tab && CASE_TABS.includes(tab) ? tab : undefined);
  }, [openCase]);

  const doAssign = async (advisor_id: string, reason: string) => {
    if (!selectedId) return;
    setAssigning(advisor_id); setActionError(null);
    try { await assignCase(selectedId, advisor_id, reason || "Assigned by staff."); await Promise.all([load(true), refreshCase(selectedId, false)]); }
    catch (e) { setActionError(e instanceof ApiError ? e.message : "The assignment did not go through. Try again."); }
    finally { setAssigning(null); }
  };

  const doAction = async (action: AdvisorAction, text?: string, compliance?: SentCompliance) => {
    if (!selectedId) return;
    setActionBusy(true); setActionError(null);
    try {
      await caseAction(selectedId, action, text, compliance);
      await Promise.all([load(true), refreshCase(selectedId, false)]);
    } catch (e) { setActionError(e instanceof ApiError ? e.message : "That did not go through. Try again."); }
    finally { setActionBusy(false); }
  };

  const isSecurity = (c: CaseRow) => c.categories?.includes("fraud_or_security");
  const isAssigned = (c: CaseRow) => c.status === "assigned" || !!c.routing?.assigned_advisor_id;
  const toAssign = (c: CaseRow) => c.lifecycle === "new" && !isSecurity(c);
  const counts = useMemo(() => ({
    all: cases.length,
    assign: cases.filter(toAssign).length,
    flagged: cases.filter((c) => (c.flags?.length || 0) > 0).length,
    security: cases.filter(isSecurity).length,
    assigned: cases.filter(isAssigned).length,
  }), [cases]);

  const filtered = useMemo(() => {
    let list = cases;
    if (filter === "assign") list = list.filter(toAssign);
    else if (filter === "flagged") list = list.filter((c) => (c.flags?.length || 0) > 0);
    else if (filter === "security") list = list.filter(isSecurity);
    else if (filter === "assigned") list = list.filter(isAssigned);
    const q = search.trim().toLowerCase();
    if (q) list = list.filter((c) =>
      c.client_display_name?.toLowerCase().includes(q) || c.case_id?.toLowerCase().includes(q) ||
      c.confirmed_plain_language_request?.toLowerCase().includes(q));
    if (sort === "priority") {
      // Most pressing first; within a level, whoever has waited longest.
      list = [...list].sort((a, b) => (a.priority?.rank ?? 2) - (b.priority?.rank ?? 2) || a.created_at.localeCompare(b.created_at));
    }
    return list;
  }, [cases, filter, search, sort]);

  const today = useMemo(() => {
    const level = (l: string) => cases.filter((c) => c.priority?.level === l).length;
    const parts = [
      level("urgent") && `${level("urgent")} urgent`,
      level("high") && `${level("high")} waiting over a day`,
      level("normal") && `${level("normal")} to work on`,
      level("low") && `${level("low")} waiting on others`,
    ].filter(Boolean) as string[];
    return parts.length ? parts.join(" · ") : "Nothing needs attention right now.";
  }, [cases]);

  const impact = useMemo(() => {
    const total = cases.length || 1;
    const clarify = cases.filter((c) => c.flags?.includes("client_term_did_not_match_account_type") || c.status?.startsWith("needs_")).length;
    const catCount: Record<string, number> = {}; const destCount: Record<string, number> = {};
    cases.forEach((c) => {
      (c.categories || []).forEach((cat) => (catCount[cat] = (catCount[cat] || 0) + 1));
      const d = c.routing?.destination || "unrouted"; destCount[d] = (destCount[d] || 0) + 1;
    });
    return {
      total: cases.length, clarifyPct: Math.round((clarify / total) * 100),
      security: cases.filter(isSecurity).length, assigned: cases.filter(isAssigned).length,
      intakes: cases.flatMap((c) => (c.intake ? [c.intake] : [])),
      categories: Object.entries(catCount).map(([k, v]) => ({ name: prettyCategory(k), value: v })).sort((a, b) => b.value - a.value),
      destinations: Object.entries(destCount).map(([k, v]) => ({ name: sentence(k), value: v })).sort((a, b) => b.value - a.value),
    };
  }, [cases]);

  const navItems: { key: Filter; label: string; icon: any; count: number }[] = [
    { key: "all", label: "All requests", icon: Inbox, count: counts.all },
    { key: "assign", label: "To assign", icon: UserPlus, count: counts.assign },
    { key: "flagged", label: "Flagged", icon: Flag, count: counts.flagged },
    { key: "security", label: "Security", icon: ShieldAlert, count: counts.security },
    { key: "assigned", label: "Assigned", icon: CheckCircle2, count: counts.assigned },
  ];
  const navClass = (active: boolean) =>
    `flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm transition-colors ${
      active ? "bg-primary/10 font-medium text-primary" : "text-foreground hover:bg-foreground/5"}`;

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="hidden w-60 shrink-0 flex-col border-r border-border bg-muted/30 p-4 md:flex">
        <div className="flex items-center gap-2 px-1">
          <img src="/coherent-icon.png" alt="Coherent" className="h-6 w-6" />
          <div>
            <div className="text-sm font-semibold leading-tight">Coherent</div>
            <div className="text-xs text-muted-foreground">Advisor workspace</div>
          </div>
        </div>
        <nav className="mt-6 space-y-1">
          {navItems.map((it) => (
            <button key={it.key} onClick={() => { setFilter(it.key); setView("queue"); }} className={navClass(view === "queue" && filter === it.key)}>
              <span className="flex items-center gap-2"><it.icon className="h-4 w-4" /> {it.label}</span>
              <span className="text-xs tabular-nums text-muted-foreground">{it.count}</span>
            </button>
          ))}
          <div className="!my-3 border-t border-border" />
          <button onClick={() => setView("pipeline")} className={navClass(view === "pipeline")}>
            <span className="flex items-center gap-2"><Columns3 className="h-4 w-4" /> Pipeline</span>
          </button>
          <button onClick={() => setView("impact")} className={navClass(view === "impact")}>
            <span className="flex items-center gap-2"><RefreshCw className="h-4 w-4" /> Impact</span>
          </button>
        </nav>
        <div className="mt-auto space-y-2 pt-6 text-xs text-muted-foreground">
          <Link href="/" className="flex items-center gap-2 hover:text-foreground"><Home className="h-3.5 w-3.5" /> Home</Link>
          <Link href="/intake" className="flex items-center gap-2 hover:text-foreground"><ArrowLeft className="h-3.5 w-3.5" /> Client intake</Link>
          <p className="pt-2 leading-relaxed">Demo workspace. All clients and data are fictional.</p>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-hidden">
        {view === "impact" ? (
          <ImpactView impact={impact} />
        ) : view === "pipeline" ? (
          <PipelineBoard cases={cases} onOpen={(id) => openCase(id)} />
        ) : (
          <div className="flex h-screen">
            {/* Queue list */}
            <section className="flex w-full max-w-sm shrink-0 flex-col border-r border-border">
              <div className="border-b border-border p-4">
                <div className="flex items-center justify-between">
                  <h1 className="text-lg font-semibold">{navItems.find((n) => n.key === filter)?.label}</h1>
                  <div className="flex rounded-lg border border-border p-0.5 text-xs" role="group" aria-label="Sort requests">
                    {(["priority", "newest"] as Sort[]).map((s) => (
                      <button key={s} onClick={() => setSort(s)} aria-pressed={sort === s}
                        className={`rounded-md px-2 py-1 ${sort === s ? "bg-primary/10 font-medium text-primary" : "text-muted-foreground hover:text-foreground"}`}>
                        {s === "priority" ? "Priority" : "Newest"}
                      </button>
                    ))}
                  </div>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{loading ? "Loading…" : today}</p>
                <div className="relative mt-3">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search by client or request" aria-label="Search requests"
                    className="w-full rounded-lg border border-border bg-background py-2 pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-primary/30" />
                </div>
              </div>
              <div className="flex-1 overflow-y-auto">
                {error && <p className="p-4 text-sm text-red-600">{error}</p>}
                {!loading && !error && filtered.length === 0 && <p className="p-4 text-sm text-muted-foreground">No requests here.</p>}
                {filtered.map((c) => {
                  const level = c.priority?.level || "normal";
                  return (
                    <button key={c.case_id} onClick={() => openCase(c.case_id)} aria-current={selectedId === c.case_id}
                      className={`block w-full border-b border-border p-4 text-left transition-colors hover:bg-foreground/[0.03] ${
                        selectedId === c.case_id ? "bg-primary/5" : ""}`}>
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="font-medium">{c.client_display_name}</span>
                        <span className="shrink-0 text-xs text-muted-foreground">{timeAgo(c.created_at)}</span>
                      </div>
                      <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{c.confirmed_plain_language_request}</p>
                      <p className={`mt-2 flex items-center gap-2 text-xs font-medium ${PRIORITY_TEXT[level]}`}>
                        <span className={`h-2 w-2 flex-none rounded-full ${PRIORITY_DOT[level]}`} />{c.priority?.reason || statusLabel(c.status)}
                      </p>
                      <div className="mt-2 flex flex-wrap items-center gap-1.5">
                        {(c.categories || []).slice(0, 2).map((cat) => (
                          <Chip key={cat} tone={cat === "fraud_or_security" ? "red" : "muted"}>{prettyCategory(cat)}</Chip>
                        ))}
                      </div>
                    </button>
                  );
                })}
              </div>
            </section>

            {/* Detail */}
            <section className="flex-1 overflow-y-auto bg-background">
              {!selectedId && (
                <div className="flex h-full flex-col items-center justify-center p-8 text-center text-muted-foreground">
                  <MessageSquareQuote className="h-8 w-8 opacity-40" />
                  <p className="mt-3 text-lg font-medium text-foreground">Select a request</p>
                  <p className="mt-1 max-w-xs text-sm">Open a request to see what the client asked, what to do next, and who should handle it.</p>
                </div>
              )}
              {selectedId && detailLoading && <p className="p-8 text-sm text-muted-foreground">Loading request…</p>}
              {selectedId && detail && !detailLoading && (
                <CaseDetail
                  key={selectedId} detail={detail} row={cases.find((c) => c.case_id === selectedId)} snapshot={snapshot}
                  candidates={candidates} candMeta={candMeta} assigning={assigning} onAssign={doAssign}
                  brief={brief} briefLoading={briefLoading}
                  onLoadBrief={() => selectedId && loadBrief(selectedId)}
                  onRegenerateBrief={() => selectedId && loadBrief(selectedId, true)}
                  plan={plan} planLoading={planLoading} planStage={planStage}
                  onRegeneratePlan={() => selectedId && loadPlan(selectedId)}
                  onApprove={async () => { await doAction("approve"); }}
                  onAction={doAction} actionBusy={actionBusy} hc={hc}
                  error={actionError} onDismissError={() => setActionError(null)}
                  onOpenCase={(id) => openCase(id)} initialTab={initialTab}
                />
              )}
            </section>
          </div>
        )}
      </main>
    </div>
  );
}

function PipelineBoard({ cases, onOpen }: { cases: CaseRow[]; onOpen: (id: string) => void }) {
  const cols = useMemo(() => {
    const m = Object.fromEntries(PIPELINE_COLS.map((c) => [c, [] as CaseRow[]])) as Record<Lifecycle, CaseRow[]>;
    cases.forEach((c) => m[c.lifecycle || "new"].push(c));
    return m;
  }, [cases]);
  return (
    <div className="h-screen overflow-auto p-8">
      <h1 className="text-2xl font-semibold">Pipeline</h1>
      <p className="mt-1 text-sm text-muted-foreground">Every request, by where it is in the advisor workflow.</p>
      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {PIPELINE_COLS.map((col) => (
          <div key={col} className="rounded-2xl border border-border bg-muted/20 p-3">
            <div className="flex items-center justify-between px-1">
              <span className="text-sm font-semibold">{LIFECYCLE_LABELS[col]}</span>
              <span className="rounded-full bg-background px-2 py-0.5 text-xs tabular-nums text-muted-foreground">{cols[col].length}</span>
            </div>
            <div className="mt-3 space-y-2">
              {cols[col].length === 0 && <p className="px-1 py-6 text-center text-xs text-muted-foreground">Nothing here</p>}
              {cols[col].map((c) => (
                <button key={c.case_id} onClick={() => onOpen(c.case_id)}
                  className="block w-full rounded-xl border border-border bg-card p-3 text-left transition-colors hover:border-primary/40">
                  <div className="text-sm font-medium">{c.client_display_name}</div>
                  <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{c.confirmed_plain_language_request}</p>
                  {(c.categories || [])[0] && <div className="mt-2"><Chip tone={c.categories?.includes("fraud_or_security") ? "red" : "muted"}>{prettyCategory(c.categories[0])}</Chip></div>}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
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
    <div className="mt-4 rounded-2xl border border-border bg-card p-5">
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

function ImpactView({ impact }: { impact: any }) {
  const intakes: { turns: number; seconds_to_confirm: number }[] = impact.intakes;
  return (
    <div className="h-screen overflow-y-auto p-8">
      <h1 className="text-2xl font-semibold">Impact</h1>
      <p className="mt-1 text-sm text-muted-foreground">Live from the request queue, plus a capacity model you can change.</p>
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
      <h2 className="mt-10 text-sm font-mono uppercase tracking-wider text-muted-foreground">Measured in this workspace</h2>
      {intakes.length === 0 ? (
        <p className="mt-4 rounded-2xl border border-border bg-card p-5 text-sm text-muted-foreground">
          No live intakes yet. Send a request from client intake and its turns and time to confirmation appear here.
        </p>
      ) : (
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Tile big={String(median(intakes.map((i) => i.turns)))} label="Median client turns to a confirmed request" tone="text-primary" />
          <Tile big={`${median(intakes.map((i) => i.seconds_to_confirm))}s`} label="Median time from first message to confirmation" tone="text-primary" />
          <Tile big={String(intakes.length)} label={`Live intake${intakes.length === 1 ? "" : "s"} measured. Seeded demo cases are excluded.`} />
        </div>
      )}
      <h2 className="mt-10 text-sm font-mono uppercase tracking-wider text-muted-foreground">Advisor capacity model</h2>
      <CapacityModel />
      <h2 className="mt-10 text-sm font-mono uppercase tracking-wider text-muted-foreground">Why it matters at scale</h2>
      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Tile big="61.2M" label="Americans are 65+, the clients who struggle most with financial terms." />
        <Tile big="<50%" label="of an advisor's time goes to direct client work today (Kitces)." />
        <Tile big="$2.6T" label="assets & about 32,500 advisors at LPL Financial alone." />
      </div>
    </div>
  );
}
