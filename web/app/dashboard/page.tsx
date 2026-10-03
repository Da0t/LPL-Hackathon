"use client";

import React, { useEffect, useMemo, useState, useCallback, useRef } from "react";
import { ArrowRight, Menu, MessageSquareQuote } from "lucide-react";
import {
  cancelAgentRuns, getCases, getCase, getCandidates, assignCase, getBrief, getPlan, caseAction, getClientSnapshot, health,
  ApiError, prettyCategory, type CaseRow, type Candidate, type Brief, type ActionPlan, type AdvisorAction,
  type ClientSnapshot, type SentCompliance,
} from "@/lib/api";
import { CaseDetail, type CaseTab } from "@/components/dashboard/case-detail";
import { ImpactView, PipelineBoard } from "@/components/dashboard/insights";
import { QueueList, type Sort } from "@/components/dashboard/queue-list";
import { FILTER_LABELS, Sidebar, type Filter, type View } from "@/components/dashboard/sidebar";
import { PRIORITY_DOT, sentence } from "@/components/dashboard/labels";

const CASE_TABS: CaseTab[] = ["overview", "plan", "client", "assign", "compliance"];

function DetailSkeleton() {
  return (
    <div role="status" aria-label="Loading request" className="mx-auto max-w-3xl animate-pulse p-6 lg:p-8">
      <div className="h-7 w-56 rounded bg-muted" />
      <div className="mt-3 h-4 w-full max-w-md rounded bg-muted" />
      <div className="mt-4 flex gap-2"><div className="h-6 w-20 rounded-md bg-muted" /><div className="h-6 w-28 rounded-md bg-muted" /><div className="h-6 w-24 rounded-md bg-muted" /></div>
      <div className="mt-8 h-9 w-full rounded bg-muted" />
      <div className="mt-6 h-48 w-full rounded-xl bg-muted" />
      <div className="mt-6 h-24 w-full rounded-xl bg-muted" />
    </div>
  );
}

export default function DashboardPage() {
  const [cases, setCases] = useState<CaseRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [sort, setSort] = useState<Sort>("priority");
  const [search, setSearch] = useState("");
  const [view, setView] = useState<View>("queue");
  // On small screens the queue and the open request take turns; this is which one is showing.
  const [pane, setPane] = useState<"list" | "detail">("list");
  const [menuOpen, setMenuOpen] = useState(false);
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

  const activeCase = useRef<string | null>(null);
  const planRun = useRef(0);
  useEffect(() => () => { if (activeCase.current) cancelAgentRuns(activeCase.current); }, []);
  const loadBrief = useCallback(async (id: string, refresh = false) => {
    setBrief(null); setBriefLoading(true);
    try { const result = await getBrief(id, refresh); if (activeCase.current === id) setBrief(result); } catch { if (activeCase.current === id) setBrief(null); } finally { if (activeCase.current === id) setBriefLoading(false); }
  }, []);

  const loadPlan = useCallback(async (id: string, refresh = false) => {
    setPlan(null); setPlanLoading(true);
    const run = ++planRun.current;
    try { const result = await getPlan(id, refresh); if (run === planRun.current && activeCase.current === id) setPlan(result); } catch { if (run === planRun.current && activeCase.current === id) setPlan(null); } finally { if (run === planRun.current && activeCase.current === id) setPlanLoading(false); }
  }, []);

  // Reloads the case without touching the brief, so acting on a case does not re-run the briefing agent.
  // Resolves to the case, or null when it could not be loaded.
  const refreshCase = useCallback(async (id: string, showLoading: boolean): Promise<any> => {
    if (showLoading) { setDetailLoading(true); setDetail(null); setCandidates([]); setCandMeta({}); setSnapshot(null); }
    try {
      const [c, cand, snap] = await Promise.all([
        getCase(id), getCandidates(id).catch(() => ({ candidates: [] })), getClientSnapshot(id).catch(() => null),
      ]);
      if (activeCase.current !== id) return null;
      setDetail(c);
      setCandidates((cand as any).candidates || []);
      setCandMeta({ destination: (cand as any).destination, reason: (cand as any).reason });
      setSnapshot(snap);
      return c;
    } catch (e) {
      if (activeCase.current !== id) return null;
      setDetail({ _error: e instanceof ApiError ? e.message : "Could not load this request." });
      return null;
    } finally { if (activeCase.current === id) setDetailLoading(false); }
  }, []);

  const openCase = useCallback((id: string, tab?: CaseTab) => {
    if (activeCase.current) cancelAgentRuns(activeCase.current);
    activeCase.current = id;
    setSelectedId(id); setInitialTab(tab); setActionError(null); setView("queue"); setPane("detail");
    window.history.replaceState(null, "", `?case=${encodeURIComponent(id)}${tab ? `&tab=${tab}` : ""}`);
    setBrief(null); setPlan(null);  // the prepared reply leads; the prep brief loads when its tab is opened
    // A request that was already answered or resolved shows what was sent, so no new reply is prepared for it.
    refreshCase(id, true).then((c) => {
      const done = (c?.history || []).some((h: any) => h.event === "action_approved" || h.event === "request_resolved");
      if (c && !done && activeCase.current === id) loadPlan(id);
    });
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

  // Resolves to the reason the action failed, or null when it went through.
  const runAction = async (action: AdvisorAction, text?: string, compliance?: SentCompliance, acknowledgedFlags?: string[]): Promise<{ code: string; message: string } | null> => {
    if (!selectedId) return { code: "NO_CASE", message: "No request is open." };
    setActionBusy(true); setActionError(null);
    try {
      await caseAction(selectedId, action, text, compliance, acknowledgedFlags, action === "approve" ? plan?.plan_id : undefined);
      await Promise.all([load(true), refreshCase(selectedId, false)]);
      return null;
    } catch (e) {
      return e instanceof ApiError ? { code: e.code, message: e.message } : { code: "UNKNOWN", message: "That did not go through. Try again." };
    } finally { setActionBusy(false); }
  };

  const doAction = async (action: AdvisorAction, text?: string, compliance?: SentCompliance) => {
    const failure = await runAction(action, text, compliance);
    if (failure) setActionError(failure.message);
  };

  // Sends the prepared reply. A failure is returned so the card can show it next to the message.
  const sendPrepared = async (message: string | undefined, reviewedChecks: string[]): Promise<string | null> => {
    const failure = await runAction("approve", message, undefined, reviewedChecks);
    if (!failure) return null;
    return failure.code === "COMPLIANCE_REVIEW_FAILED"
      ? "The compliance reviewer flagged this message, so it was not sent. Edit it and try again, or use Message client to send it with a recorded override."
      : failure.message;
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
    waiting: cases.filter((c) => c.lifecycle === "awaiting_client").length,
  }), [cases]);

  const filtered = useMemo(() => {
    let list = cases;
    if (filter === "assign") list = list.filter(toAssign);
    else if (filter === "flagged") list = list.filter((c) => (c.flags?.length || 0) > 0);
    else if (filter === "security") list = list.filter(isSecurity);
    else if (filter === "assigned") list = list.filter(isAssigned);
    else if (filter === "waiting") list = list.filter((c) => c.lifecycle === "awaiting_client");
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


  // The open request a person should start with: the top of the priority order, if anything is still pressing.
  const mostPressing = useMemo(() => {
    const open = cases.filter((c) => ["urgent", "high", "normal"].includes(c.priority?.level || "normal"));
    return [...open].sort((a, b) => (a.priority?.rank ?? 2) - (b.priority?.rank ?? 2) || a.created_at.localeCompare(b.created_at))[0];
  }, [cases]);

  const sidebar = (onClose?: () => void) => (
    <Sidebar view={view} filter={filter} counts={counts} liveModel={hc ? !!hc.live_model : undefined}
      securityUrgent={cases.some((c) => isSecurity(c) && c.priority?.level === "urgent")}
      onFilter={(f) => { setFilter(f); setView("queue"); setPane("list"); setMenuOpen(false); }}
      onView={(v) => { setView(v); setMenuOpen(false); }} onClose={onClose} />
  );

  return (
    <div className="flex h-dvh flex-col md:flex-row">
      {/* Small screens: a top bar that opens the navigation as a drawer */}
      <header className="flex flex-none items-center gap-2 border-b border-border px-3 py-2 md:hidden">
        <button onClick={() => setMenuOpen(true)} aria-label="Open menu" className="rounded-md p-2 text-foreground hover:bg-foreground/5">
          <Menu className="h-5 w-5" />
        </button>
        <img src="/coherent-icon.png" alt="" className="h-6 w-6" />
        <span className="text-sm font-semibold">{view === "queue" ? FILTER_LABELS[filter] : view === "pipeline" ? "Pipeline" : "Impact"}</span>
      </header>
      {menuOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-foreground/30" onClick={() => setMenuOpen(false)} />
          <div className="relative h-full w-64 shadow-xl">{sidebar(() => setMenuOpen(false))}</div>
        </div>
      )}
      <aside className="hidden flex-none md:block">{sidebar()}</aside>

      <main className="min-h-0 min-w-0 flex-1">
        {view === "impact" ? (
          <ImpactView impact={impact} />
        ) : view === "pipeline" ? (
          <PipelineBoard cases={cases} loading={loading} onOpen={(id) => openCase(id)} />
        ) : (
          <div className="flex h-full">
            {/* Below the lg breakpoint the queue and the open request take turns filling the screen. */}
            <section aria-label="Requests" className={`${pane === "detail" ? "hidden lg:flex" : "flex"} w-full flex-col border-border lg:w-[340px] lg:flex-none xl:w-[380px] lg:border-r`}>
              <QueueList title={FILTER_LABELS[filter]} filterKey={filter} summary={today} cases={filtered} loading={loading} error={error}
                onRetry={() => load()} selectedId={selectedId} onOpen={(id) => openCase(id)}
                search={search} onSearch={setSearch} sort={sort} onSort={setSort} />
            </section>

            <section aria-label="Request details" className={`${pane === "detail" ? "block" : "hidden lg:block"} min-w-0 flex-1 overflow-y-auto bg-background`}>
              {!selectedId && (
                <div className="flex h-full flex-col items-center justify-center p-8 text-center text-muted-foreground">
                  <MessageSquareQuote className="h-8 w-8 opacity-40" />
                  <p className="mt-3 text-lg font-medium text-foreground">Select a request</p>
                  <p className="mt-1 max-w-xs text-sm">Open a request to see what the client asked, the reply prepared for it, and who should handle it.</p>
                  {mostPressing && (
                    <button onClick={() => openCase(mostPressing.case_id)}
                      className="mt-6 flex max-w-sm items-center gap-3 rounded-xl border border-border bg-card px-4 py-3 text-left outline-none transition-colors hover:border-primary/50 focus-visible:ring-2 focus-visible:ring-primary/40">
                      <span className={`h-2 w-2 flex-none rounded-full ${PRIORITY_DOT[mostPressing.priority?.level || "normal"]}`} />
                      <span className="min-w-0">
                        <span className="block text-xs text-muted-foreground">Start with the most pressing</span>
                        <span className="block truncate text-sm font-medium text-foreground">{mostPressing.client_display_name}</span>
                        {mostPressing.priority?.reason && <span className="block truncate text-xs">{mostPressing.priority.reason}</span>}
                      </span>
                      <ArrowRight className="h-4 w-4 flex-none text-primary" />
                    </button>
                  )}
                </div>
              )}
              {selectedId && detailLoading && <DetailSkeleton />}
              {selectedId && detail && !detailLoading && (
                <CaseDetail
                  key={selectedId} detail={detail} row={cases.find((c) => c.case_id === selectedId)} snapshot={snapshot}
                  candidates={candidates} candMeta={candMeta} assigning={assigning} onAssign={doAssign}
                  brief={brief} briefLoading={briefLoading}
                  onLoadBrief={() => selectedId && loadBrief(selectedId)}
                  onRegenerateBrief={() => selectedId && loadBrief(selectedId, true)}
                  plan={plan} planLoading={planLoading}
                  onRegeneratePlan={() => selectedId && loadPlan(selectedId, true)}
                  onSendPrepared={sendPrepared}
                  onAction={doAction} actionBusy={actionBusy} hc={hc}
                  error={actionError} onDismissError={() => setActionError(null)}
                  onOpenCase={(id) => openCase(id)} initialTab={initialTab}
                  onBack={() => setPane("list")}
                />
              )}
            </section>
          </div>
        )}
      </main>
    </div>
  );
}
