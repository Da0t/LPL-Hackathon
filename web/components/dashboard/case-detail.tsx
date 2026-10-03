"use client";

import React, { useState } from "react";
import {
  CheckCircle2, Hand, StickyNote, CalendarCheck, CheckCheck, PenLine, X, AlertTriangle, Sparkles, Workflow,
  ArrowLeft, ShieldAlert, UserCheck, UserPlus,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  prettyCategory, type ActionPlan, type AdvisorAction, type Brief, type Candidate, type CaseRow, type ClientSnapshot, type SentCompliance,
} from "@/lib/api";
import { AgentCard, Chip, Section, Subheading } from "./section";
import { ActionPacket } from "./action-packet";
import { ReplyPanel } from "./reply-panel";
import { CompliancePanel } from "./compliance-panel";
import { NextStepsPanel } from "./next-steps-panel";
import { InvestigationPanel } from "./investigation-panel";
import { ClientSnapshotPanel } from "./client-snapshot";
import {
  HISTORY_LABELS, PRIORITY_DOT, agentNote, PRIORITY_TEXT, flagLabel, money, prettyDate, sentence, statusLabel, timeAgo,
} from "./labels";

export type CaseTab = "overview" | "client" | "plan" | "assign" | "compliance";
const TABS: { key: CaseTab; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "plan", label: "Next steps" },
  { key: "client", label: "Client" },
  { key: "assign", label: "Assign" },
  { key: "compliance", label: "Compliance & history" },
];

function PrepBrief({ brief, loading, onRegenerate }: { brief: Brief | null; loading: boolean; onRegenerate: () => void }) {
  return (
    <AgentCard title="Prep brief" agent="Briefing agent" loading={loading} onRefresh={onRegenerate}>
      {loading && <p className="text-sm text-muted-foreground">Preparing you for this conversation…</p>}
      {!loading && !brief && <p className="text-sm text-muted-foreground">The prep brief is unavailable right now. Try Regenerate.</p>}
      {!loading && brief && (
        <div className="space-y-4">
          <p className="text-sm font-medium text-foreground">{brief.headline}</p>
          {brief.talking_points?.length > 0 && (
            <div>
              <Subheading>Talking points</Subheading>
              <ul className="mt-1.5 space-y-1.5">
                {brief.talking_points.map((t, i) => (
                  <li key={i} className="flex gap-2 text-sm"><span className="mt-2 h-1 w-1 flex-none rounded-full bg-primary" />{t}</li>
                ))}
              </ul>
            </div>
          )}
          {brief.confirm?.length > 0 && (
            <div>
              <Subheading>Confirm with the client</Subheading>
              <ul className="mt-1.5 space-y-1.5">
                {brief.confirm.map((t, i) => (
                  <li key={i} className="flex gap-2 text-sm"><CheckCircle2 className="mt-0.5 h-4 w-4 flex-none text-primary/70" />{t}</li>
                ))}
              </ul>
            </div>
          )}
          {brief.cautions?.length > 0 && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
              <p className="text-xs font-semibold text-amber-800">Compliance cautions</p>
              <ul className="mt-1.5 space-y-1">
                {brief.cautions.map((t, i) => <li key={i} className="text-sm text-amber-900">• {t}</li>)}
              </ul>
            </div>
          )}
          {brief.note && <p className="text-xs text-muted-foreground">{agentNote(brief.ai_mode, brief.note)}</p>}
        </div>
      )}
    </AgentCard>
  );
}

function ActionBar({ onAction, onDraftReply, busy, replyOpen, resolved }: {
  onAction: (a: AdvisorAction, t?: string) => void; onDraftReply: () => void; busy: boolean; replyOpen: boolean; resolved: boolean;
}) {
  const [open, setOpen] = useState<AdvisorAction | null>(null);
  const [text, setText] = useState("");
  const forms: Partial<Record<AdvisorAction, { prompt: string; required: boolean }>> = {
    note: { prompt: "Add an internal note. Only staff can see it.", required: true },
    schedule: { prompt: "Meeting details (optional), e.g. ‘Phone, Thursday 2pm’.", required: false },
    resolve: { prompt: "How was this resolved?", required: true },
  };
  const form = open ? forms[open] : undefined;
  const toggle = (a: AdvisorAction) => { setText(""); setOpen(open === a ? null : a); };
  const submit = () => { if (open) { onAction(open, text.trim() || undefined); setOpen(null); setText(""); } };
  return (
    <div className="mt-4">
      <div className="flex flex-wrap gap-2" role="toolbar" aria-label="Request actions">
        <Button size="sm" variant={replyOpen ? "default" : "secondary"} disabled={busy || resolved} onClick={() => { setOpen(null); onDraftReply(); }}>
          <PenLine className="mr-1.5 h-4 w-4" />Message client
        </Button>
        <Button size="sm" variant="secondary" disabled={busy || resolved} onClick={() => onAction("claim")}><Hand className="mr-1.5 h-4 w-4" />Claim</Button>
        <Button size="sm" variant="secondary" disabled={busy} onClick={() => toggle("note")}><StickyNote className="mr-1.5 h-4 w-4" />Add note</Button>
        <Button size="sm" variant="secondary" disabled={busy || resolved} onClick={() => toggle("schedule")}><CalendarCheck className="mr-1.5 h-4 w-4" />Mark scheduled</Button>
        <Button size="sm" variant="secondary" disabled={busy || resolved} onClick={() => toggle("resolve")}><CheckCheck className="mr-1.5 h-4 w-4" />Resolve</Button>
      </div>
      {resolved && <p className="mt-2 text-xs text-muted-foreground">This request is resolved. You can still add a note.</p>}
      {open && form && (
        <div className="mt-3">
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={2} maxLength={2000} placeholder={form.prompt} autoFocus
            className="w-full rounded-lg border border-border bg-background p-2.5 text-sm outline-none focus:ring-2 focus:ring-primary/30" />
          <div className="mt-2 flex gap-2">
            <Button size="sm" disabled={busy || (form.required && !text.trim())} onClick={submit}>{busy ? "Saving…" : "Save"}</Button>
            <Button size="sm" variant="ghost" onClick={() => { setOpen(null); setText(""); }}>Cancel</Button>
          </div>
        </div>
      )}
    </div>
  );
}

// The one thing this request needs from whoever opened it. Triage steps come first: a request nobody
// owns, or a security concern that has not reached the specialists, outranks everything else on the page.
function NextAction({ security, escalated, top, candidateCount, assigning, actionBusy, onAssign, onAction, onShowTab }: {
  security: boolean; escalated: boolean; top?: Candidate; candidateCount: number; assigning: string | null; actionBusy: boolean;
  onAssign: (advisorId: string, reason: string) => void; onAction: (a: AdvisorAction) => void; onShowTab: (t: CaseTab) => void;
}) {
  if (security) {
    if (escalated) return null;
    return (
      <div className="mt-5 rounded-xl border border-red-200 bg-red-50 p-4">
        <p className="flex items-center gap-2 text-sm font-semibold text-red-800"><ShieldAlert className="h-4 w-4 text-red-600" />Possible security issue</p>
        <p className="mt-1 text-sm text-red-700">This goes to the security specialist team, not a general advisor. Send it before anything else.</p>
        <div className="mt-3 flex flex-wrap items-center gap-4">
          <Button size="sm" variant="destructive" disabled={actionBusy} onClick={() => onAction("escalate")}>
            {actionBusy ? "Sending…" : "Send to the security team"}
          </Button>
          <button onClick={() => onShowTab("plan")} className="text-sm font-medium text-red-700 underline-offset-2 hover:underline">See the security review</button>
        </div>
      </div>
    );
  }
  return (
    <div className="mt-5 rounded-xl border border-primary/30 bg-primary/[0.04] p-4">
      <p className="flex items-center gap-2 text-sm font-semibold"><UserPlus className="h-4 w-4 text-primary" />No advisor is handling this yet</p>
      {top ? (
        <div className="mt-3 flex flex-wrap items-start justify-between gap-x-4 gap-y-3">
          <div className="min-w-0 flex-1 basis-64">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-muted-foreground">Recommended</span>
              <span className="text-sm font-medium">{top.display_name}</span>
              {top.available ? <Chip tone="green">Available</Chip> : <Chip tone="amber">At capacity</Chip>}
              {top.existing_client_relationship && <Chip>Knows this client</Chip>}
            </div>
            <p className="mt-1 text-sm text-muted-foreground">{top.reason}</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {candidateCount > 1 && (
              <button onClick={() => onShowTab("assign")} className="text-sm font-medium text-primary underline-offset-2 hover:underline">
                Compare all {candidateCount}
              </button>
            )}
            <Button size="sm" disabled={!!assigning} onClick={() => onAssign(top.advisor_id, top.reason)}>
              {assigning === top.advisor_id ? "Assigning…" : `Assign to ${top.display_name.split(" ")[0]}`}
            </Button>
          </div>
        </div>
      ) : (
        <p className="mt-1 text-sm text-muted-foreground">
          No advisors were recommended for this request.{" "}
          <button onClick={() => onShowTab("assign")} className="font-medium text-primary underline-offset-2 hover:underline">See where it is routed</button>
        </p>
      )}
    </div>
  );
}

function Activity({ history }: { history: any[] }) {
  if (!history?.length) return null;
  return (
    <Section title="History">
      <ol className="space-y-3 border-l border-border pl-4">
        {[...history].reverse().map((h, i) => (
          <li key={i} className="relative">
            <span className="absolute -left-[21px] top-1.5 h-2 w-2 rounded-full bg-primary/50" />
            <div className="text-sm font-medium">{HISTORY_LABELS[h.event] || sentence(h.event)}</div>
            {h.details?.text && <div className="text-sm text-muted-foreground">“{h.details.text}”</div>}
            {h.details?.acknowledged_flags?.length > 0 && (
              <div className="text-xs text-muted-foreground">Flagged items signed off: {h.details.acknowledged_flags.join(", ")}</div>
            )}
            {h.details?.compliance && (
              <div className="text-xs text-muted-foreground">
                Compliance review: {h.details.compliance.verdict === "pass" ? "passed" : "flagged"}
                {h.details.compliance.override ? ", sent with an advisor override" : ""}
              </div>
            )}
            <div className="text-xs text-muted-foreground">{timeAgo(h.at)}</div>
          </li>
        ))}
      </ol>
    </Section>
  );
}

function Overview({ detail, brief, briefLoading, onLoadBrief, onRegenerateBrief, plan, planLoading, onRegeneratePlan, onSendPrepared }: any) {
  const [lead, setLead] = useState<"action" | "brief">("action");
  const ac = detail.account_context;
  const flags: string[] = detail.flags || [];
  const leadClass = (active: boolean) =>
    `flex items-center gap-1.5 rounded-lg px-3 py-1.5 font-medium transition-colors ${active ? "bg-background text-primary shadow-sm" : "text-muted-foreground hover:text-foreground"}`;
  return (
    <>
      {/* Prepared reply (default) | prep brief */}
      <div className="mt-5 inline-flex rounded-xl border border-border bg-muted/40 p-1 text-sm">
        <button onClick={() => setLead("action")} className={leadClass(lead === "action")}>
          <Workflow className="h-4 w-4" /> Prepared reply
        </button>
        <button onClick={() => { setLead("brief"); if (!brief && !briefLoading) onLoadBrief(); }} className={leadClass(lead === "brief")}>
          <Sparkles className="h-4 w-4" /> Prep brief
        </button>
      </div>
      {lead === "action"
        ? <ActionPacket plan={plan} loading={planLoading} onRegenerate={onRegeneratePlan} onSend={onSendPrepared}
            sent={(detail.history || []).find((h: any) => h.event === "action_approved") || null}
            resolved={(detail.history || []).some((h: any) => h.event === "request_resolved")} />
        : <div className="mt-5"><PrepBrief brief={brief} loading={briefLoading} onRegenerate={onRegenerateBrief} /></div>}

      <Section title="In the client's own words">
        <blockquote className="rounded-lg border-l-2 border-primary bg-muted/40 p-3 text-sm italic">“{detail.original_words}”</blockquote>
        <p className="mt-2 text-xs text-muted-foreground">The client confirmed the plain-language version at the top of this request.</p>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {(detail.categories || []).map((c: string) => <Chip key={c} tone={c === "fraud_or_security" ? "red" : "muted"}>{prettyCategory(c)}</Chip>)}
        </div>
      </Section>

      {(flags.length > 0 || (detail.conflicts || []).length > 0 || (detail.unresolved_questions || []).length > 0) && (
        <Section title="Things to know before you call">
          <ul className="space-y-2">
            {flags.map((f) => (
              <li key={f} className="flex gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                <AlertTriangle className="mt-0.5 h-4 w-4 flex-none" />{flagLabel(f)}
              </li>
            ))}
            {(detail.conflicts || []).map((c: any, i: number) => (
              <li key={`c${i}`} className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                {c.statement} <span className="text-xs opacity-70">(source {c.source_id})</span>
              </li>
            ))}
          </ul>
          {(detail.unresolved_questions || []).length > 0 && (
            <div className="mt-3">
              <p className="text-xs text-muted-foreground">Still open</p>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">
                {detail.unresolved_questions.map((q: string, i: number) => <li key={i}>{q}</li>)}
              </ul>
            </div>
          )}
        </Section>
      )}

      {ac && (
        <Section title="Account on record">
          <div className="rounded-xl border border-border bg-card p-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <div className="text-sm font-medium">{ac.account_label || sentence(ac.account_type || "")} <span className="font-normal text-muted-foreground">{ac.masked_identifier}</span></div>
              {typeof ac.balance === "number" && (
                <div className="text-sm"><span className="font-medium tabular-nums">{money(ac.balance)}</span> <span className="text-xs text-muted-foreground">as of {prettyDate(ac.balance_as_of)}</span></div>
              )}
            </div>
            {(ac.relevant_events || []).length > 0 && (
              <ul className="mt-3 space-y-1 border-t border-border pt-3 text-sm text-muted-foreground">
                {ac.relevant_events.map((e: any, i: number) => <li key={i}>{sentence(e.type)} · {prettyDate(e.date)}</li>)}
              </ul>
            )}
            <p className="mt-3 text-xs text-muted-foreground">From the firm's records. The balance is context, not an amount available to withdraw.</p>
          </div>
        </Section>
      )}

      {detail.staff_summary && <Section title="Summary for staff"><p className="text-sm text-muted-foreground">{detail.staff_summary}</p></Section>}
    </>
  );
}

function Assign({ detail, candidates, candMeta, assigning, onAssign, onAction, actionBusy, security, assignedName }: any) {
  const assignedId = detail.routing?.assigned_advisor_id;
  const assigned = !!assignedId;
  const escalated = (detail.history || []).some((h: any) => h.event === "escalated_to_security");
  // Routing reasons arrive with raw category codes in quotes; show the category's name instead.
  const reason = (detail.routing?.reason || candMeta.reason || "").replace(/'([a-z_]+)'/g, (_: string, c: string) => `“${prettyCategory(c)}”`);
  return (
    <>
      <Section title="Where this request is routed">
        <div className="rounded-xl border border-border bg-card p-4">
          <p className={`text-sm font-medium ${security ? "text-red-700" : ""}`}>{sentence(detail.routing?.destination || candMeta.destination || "Not routed yet")}</p>
          {reason && <p className="mt-1 text-sm text-muted-foreground">{reason}</p>}
          {assigned && <p className="mt-3 flex items-center gap-1.5 text-sm font-medium text-emerald-700"><CheckCircle2 className="h-4 w-4" />Assigned to {assignedName}</p>}
        </div>
      </Section>
      <Section title={security ? "Specialist review" : "Recommended advisors"}>
        {security ? (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            <p>This request involves a possible security concern. It goes to the <b>security specialist team</b>, not a general advisor.</p>
            {escalated ? (
              <p className="mt-3 flex items-center gap-1.5 font-medium text-emerald-700"><CheckCircle2 className="h-4 w-4" />Sent to the security specialist team</p>
            ) : (
              <Button size="sm" className="mt-3" disabled={actionBusy} onClick={() => onAction("escalate")}>
                {actionBusy ? "Sending…" : "Send to the security team"}
              </Button>
            )}
          </div>
        ) : candidates.length === 0 ? (
          <p className="text-sm text-muted-foreground">No advisors were recommended for this request.</p>
        ) : (
          <div className="space-y-3">
            {candidates.map((a: Candidate) => (
              <div key={a.advisor_id} className="flex items-start justify-between gap-4 rounded-xl border border-border bg-card p-4">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium">{a.display_name}</span>
                    {a.available ? <Chip tone="green">Available</Chip> : <Chip tone="amber">At capacity</Chip>}
                    {a.existing_client_relationship && <Chip>Knows this client</Chip>}
                  </div>
                  <div className="mt-1.5 flex flex-wrap gap-1">{(a.specialties || []).map((s) => <Chip key={s}>{prettyCategory(s)}</Chip>)}</div>
                  <p className="mt-2 text-sm text-muted-foreground">{a.reason}</p>
                </div>
                <Button size="sm" className="shrink-0" variant={assigned && assignedId !== a.advisor_id ? "outline" : "default"}
                  disabled={!!assigning || assignedId === a.advisor_id} onClick={() => onAssign(a.advisor_id, a.reason)}>
                  {assigning === a.advisor_id ? "Assigning…" : assignedId === a.advisor_id ? "Assigned" : assigned ? "Reassign" : "Assign"}
                </Button>
              </div>
            ))}
          </div>
        )}
      </Section>
    </>
  );
}

export function CaseDetail({
  detail, row, snapshot, candidates, candMeta, assigning, onAssign, brief, briefLoading, onLoadBrief, onRegenerateBrief,
  plan, planLoading, onRegeneratePlan, onSendPrepared, onAction, actionBusy, hc, error, onDismissError, onOpenCase, initialTab, onBack,
}: {
  detail: any; row?: CaseRow; snapshot: ClientSnapshot | null; candidates: Candidate[];
  candMeta: { destination?: string; reason?: string }; assigning: string | null;
  onAssign: (advisorId: string, reason: string) => void; brief: Brief | null; briefLoading: boolean;
  onLoadBrief: () => void; onRegenerateBrief: () => void;
  plan: ActionPlan | null; planLoading: boolean; onRegeneratePlan: () => void;
  onSendPrepared: (message: string | undefined, reviewedChecks: string[]) => Promise<string | null>;
  onAction: (a: AdvisorAction, t?: string, c?: SentCompliance) => void;
  actionBusy: boolean; hc: any; error: string | null; onDismissError: () => void;
  onOpenCase: (id: string) => void; initialTab?: CaseTab;
  /** Returns to the queue on screens too narrow to show both. */
  onBack?: () => void;
}) {
  const [tab, setTab] = useState<CaseTab>(initialTab || "overview");
  const [replyOpen, setReplyOpen] = useState(false);
  if (detail._error) return <p className="p-8 text-sm text-red-600">{detail._error}</p>;

  const security = detail.categories?.includes("fraud_or_security");
  const assignedId = detail.routing?.assigned_advisor_id;
  const assignedName = snapshot?.assigned_advisor?.display_name
    || candidates.find((c) => c.advisor_id === assignedId)?.display_name || "an advisor";
  const priority = row?.priority;
  const history: any[] = detail.history || [];
  const resolved = history.some((h) => h.event === "request_resolved");
  const escalated = history.some((h) => h.event === "escalated_to_security");
  const needsTriage = !resolved && (security ? !escalated : !assignedId);
  const showTab = (t: CaseTab) => setTab(t);

  return (
    <div className="mx-auto max-w-3xl px-5 pb-16 pt-4 lg:px-8 lg:pt-8">
      {onBack && (
        <button onClick={onBack} className="-ml-1.5 mb-3 flex items-center gap-1.5 rounded-md px-1.5 py-1 text-sm text-muted-foreground hover:text-foreground lg:hidden">
          <ArrowLeft className="h-4 w-4" /> Requests
        </button>
      )}
      <h2 className="text-2xl font-semibold tracking-tight">{detail.client_display_name}</h2>
      <p className="mt-1.5 text-[15px] leading-relaxed text-foreground/85">{detail.confirmed_plain_language_request}</p>
      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        {priority && (
          <span className={`flex items-center gap-1.5 whitespace-nowrap rounded-md border border-border bg-card px-2 py-0.5 text-xs font-medium ${PRIORITY_TEXT[priority.level]}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${PRIORITY_DOT[priority.level]}`} />{priority.reason}
          </span>
        )}
        {!assignedId && <Chip>{statusLabel(detail.status)}</Chip>}
        {assignedId ? (
          <Chip tone="green"><UserCheck className="-mt-0.5 mr-1 inline h-3 w-3" />{assignedName}</Chip>
        ) : !security && !resolved ? (
          <span className="whitespace-nowrap rounded-md border border-dashed border-primary/40 px-2 py-0.5 text-xs text-primary">Unassigned</span>
        ) : null}
      </div>
      <p className="mt-2 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
        <span>Received {timeAgo(detail.created_at)}</span>
        {row?.intake && <span>Intake took {row.intake.turns} turn{row.intake.turns === 1 ? "" : "s"} and {row.intake.seconds_to_confirm}s</span>}
        <span className="tabular-nums">{detail.case_id}</span>
      </p>

      {error && (
        <div role="alert" className="mt-4 flex items-start justify-between gap-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          <span>{error}</span>
          <button onClick={onDismissError} aria-label="Dismiss"><X className="h-4 w-4" /></button>
        </div>
      )}

      {needsTriage && (
        <NextAction security={!!security} escalated={escalated} top={candidates[0]} candidateCount={candidates.length}
          assigning={assigning} actionBusy={actionBusy} onAssign={onAssign} onAction={onAction} onShowTab={showTab} />
      )}

      <ActionBar onAction={onAction} onDraftReply={() => setReplyOpen((v) => !v)} busy={actionBusy} replyOpen={replyOpen} resolved={resolved} />
      {replyOpen && !resolved && (
        <ReplyPanel caseId={detail.case_id} busy={actionBusy} onClose={() => setReplyOpen(false)}
          onSend={(text, compliance) => onAction("clarify", text, compliance)} />
      )}

      <div role="tablist" className="sticky top-0 z-10 -mx-1 mt-6 flex gap-1 overflow-x-auto border-b border-border bg-background px-1">
        {TABS.map((t) => (
          <button key={t.key} role="tab" aria-selected={tab === t.key} onClick={() => setTab(t.key)}
            className={`-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
              tab === t.key ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"}`}>
            {t.key === "plan" && security ? "Security review" : t.label}
            {t.key === "assign" && needsTriage && <span aria-label="needs attention" className="ml-1.5 inline-block h-1.5 w-1.5 rounded-full bg-primary align-middle" />}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <Overview detail={detail} brief={brief} briefLoading={briefLoading} onLoadBrief={onLoadBrief} onRegenerateBrief={onRegenerateBrief}
          plan={plan} planLoading={planLoading} onRegeneratePlan={onRegeneratePlan} onSendPrepared={onSendPrepared} />
      )}
      {tab === "plan" && (
        <div className="mt-6 space-y-6">
          {security && <InvestigationPanel caseId={detail.case_id} />}
          <NextStepsPanel caseId={detail.case_id} />
        </div>
      )}
      {tab === "client" && <ClientSnapshotPanel snapshot={snapshot} onOpenCase={onOpenCase} />}
      {tab === "assign" && (
        <Assign detail={detail} candidates={candidates} candMeta={candMeta} assigning={assigning} onAssign={onAssign}
          onAction={onAction} actionBusy={actionBusy} security={security} assignedName={assignedName} />
      )}
      {tab === "compliance" && (
        <>
          <CompliancePanel detail={detail} hc={hc} />
          <Activity history={detail.history || []} />
        </>
      )}
    </div>
  );
}
