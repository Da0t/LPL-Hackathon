"use client";

import React, { useState } from "react";
import {
  CheckCircle2, Hand, StickyNote, Send, CalendarCheck, CheckCheck, PenLine, X, AlertTriangle, Sparkles, Workflow,
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
              <p className="text-xs font-semibold uppercase tracking-wide text-amber-800">Compliance cautions</p>
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

function ActionBar({ onAction, onDraftReply, busy, replyOpen }: {
  onAction: (a: AdvisorAction, t?: string) => void; onDraftReply: () => void; busy: boolean; replyOpen: boolean;
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
    <div className="mt-5 rounded-2xl border border-border bg-muted/20 p-3">
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant={replyOpen ? "default" : "outline"} disabled={busy} onClick={() => { setOpen(null); onDraftReply(); }}>
          <PenLine className="mr-1.5 h-4 w-4" />Message client
        </Button>
        <Button size="sm" variant="outline" disabled={busy} onClick={() => onAction("claim")}><Hand className="mr-1.5 h-4 w-4" />Claim</Button>
        <Button size="sm" variant="outline" disabled={busy} onClick={() => toggle("note")}><StickyNote className="mr-1.5 h-4 w-4" />Add note</Button>
        <Button size="sm" variant="outline" disabled={busy} onClick={() => toggle("schedule")}><CalendarCheck className="mr-1.5 h-4 w-4" />Mark scheduled</Button>
        <Button size="sm" variant="outline" disabled={busy} onClick={() => toggle("resolve")}><CheckCheck className="mr-1.5 h-4 w-4" />Resolve</Button>
      </div>
      {open && form && (
        <div className="mt-3">
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={2} placeholder={form.prompt} autoFocus
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

function Overview({ detail, brief, briefLoading, onLoadBrief, onRegenerateBrief, plan, planLoading, planStage, onRegeneratePlan, onApprove }: any) {
  const [lead, setLead] = useState<"action" | "brief">("action");
  const ac = detail.account_context;
  const flags: string[] = detail.flags || [];
  const leadClass = (active: boolean) =>
    `flex items-center gap-1.5 rounded-lg px-3 py-1.5 font-medium transition-colors ${active ? "bg-background text-primary shadow-sm" : "text-muted-foreground hover:text-foreground"}`;
  return (
    <>
      {/* Prepared action (default) | prep brief, as on main */}
      <div className="mt-5 inline-flex rounded-xl border border-border bg-muted/40 p-1 text-sm">
        <button onClick={() => setLead("action")} className={leadClass(lead === "action")}>
          <Workflow className="h-4 w-4" /> Prepared action
        </button>
        <button onClick={() => { setLead("brief"); if (!brief && !briefLoading) onLoadBrief(); }} className={leadClass(lead === "brief")}>
          <Sparkles className="h-4 w-4" /> Prep brief
        </button>
      </div>
      {lead === "action"
        ? <ActionPacket plan={plan} loading={planLoading} stage={planStage} onRegenerate={onRegeneratePlan} onApprove={onApprove} />
        : <div className="mt-5"><PrepBrief brief={brief} loading={briefLoading} onRegenerate={onRegenerateBrief} /></div>}

      <Section title="What the client asked">
        <blockquote className="rounded-lg border-l-2 border-primary bg-muted/40 p-3 text-sm italic">“{detail.original_words}”</blockquote>
        <p className="mt-3 text-xs text-muted-foreground">Confirmed by the client as</p>
        <p className="text-sm">{detail.confirmed_plain_language_request}</p>
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
          <div className="rounded-2xl border border-border bg-card p-4">
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
        <div className="rounded-2xl border border-border bg-card p-4">
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
              <div key={a.advisor_id} className="flex items-start justify-between gap-4 rounded-2xl border border-border bg-card p-4">
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
  plan, planLoading, planStage, onRegeneratePlan, onApprove, onAction, actionBusy, hc, error, onDismissError, onOpenCase, initialTab,
}: {
  detail: any; row?: CaseRow; snapshot: ClientSnapshot | null; candidates: Candidate[];
  candMeta: { destination?: string; reason?: string }; assigning: string | null;
  onAssign: (advisorId: string, reason: string) => void; brief: Brief | null; briefLoading: boolean;
  onLoadBrief: () => void; onRegenerateBrief: () => void;
  plan: ActionPlan | null; planLoading: boolean; planStage: number; onRegeneratePlan: () => void; onApprove: () => Promise<void>;
  onAction: (a: AdvisorAction, t?: string, c?: SentCompliance) => void;
  actionBusy: boolean; hc: any; error: string | null; onDismissError: () => void;
  onOpenCase: (id: string) => void; initialTab?: CaseTab;
}) {
  const [tab, setTab] = useState<CaseTab>(initialTab || "overview");
  const [replyOpen, setReplyOpen] = useState(false);
  if (detail._error) return <p className="p-8 text-sm text-red-600">{detail._error}</p>;

  const security = detail.categories?.includes("fraud_or_security");
  const assignedId = detail.routing?.assigned_advisor_id;
  const assignedName = snapshot?.assigned_advisor?.display_name
    || candidates.find((c) => c.advisor_id === assignedId)?.display_name || "an advisor";
  const priority = row?.priority;

  return (
    <div className="mx-auto max-w-3xl p-6 lg:p-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">{detail.client_display_name}</h2>
          <p className="mt-1 flex flex-wrap items-center gap-x-2 text-sm text-muted-foreground">
            <span>{statusLabel(detail.status)}</span>
            {assignedId && <span>· {assignedName}</span>}
            <span>· Received {timeAgo(detail.created_at)}</span>
            {row?.intake && <span>· Intake took {row.intake.turns} turn{row.intake.turns === 1 ? "" : "s"}, {row.intake.seconds_to_confirm}s</span>}
            <span className="text-xs">· {detail.case_id}</span>
          </p>
        </div>
        {priority && (
          <span className={`flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-sm ${PRIORITY_TEXT[priority.level]}`}>
            <span className={`h-2 w-2 rounded-full ${PRIORITY_DOT[priority.level]}`} />{priority.reason}
          </span>
        )}
      </div>

      {error && (
        <div role="alert" className="mt-4 flex items-start justify-between gap-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          <span>{error}</span>
          <button onClick={onDismissError} aria-label="Dismiss"><X className="h-4 w-4" /></button>
        </div>
      )}

      <ActionBar onAction={onAction} onDraftReply={() => setReplyOpen((v) => !v)} busy={actionBusy} replyOpen={replyOpen} />
      {replyOpen && (
        <ReplyPanel caseId={detail.case_id} busy={actionBusy} onClose={() => setReplyOpen(false)}
          onSend={(text, compliance) => onAction("clarify", text, compliance)} />
      )}

      <div role="tablist" className="mt-6 flex gap-1 overflow-x-auto border-b border-border">
        {TABS.map((t) => (
          <button key={t.key} role="tab" aria-selected={tab === t.key} onClick={() => setTab(t.key)}
            className={`-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
              tab === t.key ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"}`}>
            {t.key === "plan" && security ? "Security review" : t.label}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <Overview detail={detail} brief={brief} briefLoading={briefLoading} onLoadBrief={onLoadBrief} onRegenerateBrief={onRegenerateBrief}
          plan={plan} planLoading={planLoading} planStage={planStage} onRegeneratePlan={onRegeneratePlan} onApprove={onApprove} />
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
