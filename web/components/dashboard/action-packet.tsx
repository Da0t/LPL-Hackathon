"use client";

// The fulfillment agent's prepared action packet, as built on main: pipeline animation,
// pre-filled fields, auto-run compliance checks, drafts, and the approve step.
import React, { useEffect, useState } from "react";
import {
  CheckCircle2, RefreshCw, Clock, ShieldCheck,
  Brain, Layers, ClipboardList, PenLine, Loader2, Copy, Check, AlertTriangle, Workflow,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { AgentEvidence, AuditVerdict } from "./agent-evidence";
import type { ActionPlan } from "@/lib/api";

const PIPELINE_STEPS = [
  { label: "Forge prepares", icon: ClipboardList },
  { label: "Verifier audits", icon: ShieldCheck },
];

function AgentPipeline({ stage, done }: { stage: number; done: boolean }) {
  const completed = done ? PIPELINE_STEPS.length : stage;
  return (
    <div className="flex items-center justify-between gap-1 rounded-2xl border border-border bg-muted/20 p-3">
      {PIPELINE_STEPS.map((s, i) => {
        const isDone = i < completed;
        const isRunning = !done && i === completed;
        return (
          <React.Fragment key={s.label}>
            <div className="flex flex-1 flex-col items-center gap-1.5 text-center">
              <div className={`flex h-9 w-9 items-center justify-center rounded-full border transition-all duration-300 ${
                isDone ? "border-primary bg-primary text-white shadow-[0_0_14px_rgba(22,119,255,0.4)]"
                : isRunning ? "border-primary bg-primary/10 text-primary shadow-[0_0_14px_rgba(22,119,255,0.3)]"
                : "border-border bg-background text-muted-foreground"}`}>
                {isDone ? <Check className="h-4 w-4" /> : isRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <s.icon className="h-4 w-4" />}
              </div>
              <span className={`text-[10px] leading-tight ${isDone || isRunning ? "text-foreground" : "text-muted-foreground"}`}>{s.label}</span>
            </div>
            {i < PIPELINE_STEPS.length - 1 && <div className={`mb-4 h-px flex-1 transition-colors duration-300 ${i < completed ? "bg-primary" : "bg-border"}`} />}
          </React.Fragment>
        );
      })}
    </div>
  );
}

function CopyCard({ title, text }: { title: string; text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => { try { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { /* clipboard blocked */ } };
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">{title}</p>
        <button onClick={copy} className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
          {copied ? <Check className="h-3 w-3 text-primary" /> : <Copy className="h-3 w-3" />}{copied ? "Copied" : "Copy"}
        </button>
      </div>
      <p className="mt-2 whitespace-pre-wrap text-sm text-foreground">{text}</p>
    </div>
  );
}

function ComplianceBadge({ status }: { status: string }) {
  const map: Record<string, { cls: string; icon: any; label: string }> = {
    pass: { cls: "bg-emerald-50 text-emerald-700 border-emerald-200", icon: CheckCircle2, label: "Pass" },
    review: { cls: "bg-amber-50 text-amber-700 border-amber-200", icon: Clock, label: "Review" },
    flag: { cls: "bg-red-50 text-red-600 border-red-200", icon: AlertTriangle, label: "Flag" },
  };
  const m = map[status] || map.review;
  return <span className={`inline-flex flex-none items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] font-medium ${m.cls}`}><m.icon className="h-3 w-3" />{m.label}</span>;
}

export function ActionPacket({ caseId, plan, loading, stage, onRegenerate, onApprove }: { caseId: string; plan: ActionPlan | null; loading: boolean; stage: number; onRegenerate: () => void; onApprove: () => Promise<void> }) {
  const [approving, setApproving] = useState(false);
  const [approved, setApproved] = useState(false);
  useEffect(() => { setApproved(false); }, [plan]);
  const approve = async () => { setApproving(true); try { await onApprove(); setApproved(true); } catch { /* Parent displays the approval error. */ } finally { setApproving(false); } };
  const actionTitle = (plan?.action_type || "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  return (
    <div className="mt-5 overflow-hidden rounded-2xl border border-primary/30 bg-primary/[0.03]">
      <div className="flex items-center justify-between border-b border-primary/15 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <Workflow className="h-4 w-4 text-primary" />
          <span className="text-sm font-semibold">Agent prepared this action</span>
          <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">{plan?.note ? "Fallback preparation" : plan?.ai_mode === "bedrock" ? "Amazon Bedrock" : "Offline record checks"}</span>
        </div>
        <button onClick={onRegenerate} disabled={loading} className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground disabled:opacity-50">
          <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} /> {loading ? "Working…" : "Regenerate"}
        </button>
      </div>
      <div className="space-y-4 p-4">
        <AgentEvidence caseId={caseId} operation="plan" />
        {!loading && plan && <AuditVerdict audit={plan.audit} />}
        <AgentPipeline stage={stage} done={!loading && !!plan} />
        {loading && <p className="text-center text-sm text-muted-foreground">Agents are preparing the packet and independently checking its facts…</p>}
        {!loading && !plan && <p className="text-sm text-muted-foreground">Couldn't prepare this action right now. Try Regenerate.</p>}
        {!loading && plan && plan.audit?.verdict !== "pass" && <p className="text-sm">The packet is withheld. Review the findings and regenerate after correcting the record.</p>}
        {!loading && plan && plan.audit?.verdict === "pass" && (
          <>
            <div className="rounded-xl border border-border bg-card p-4">
              <span className="rounded-md bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary">{actionTitle}</span>
              <p className="mt-2 text-sm font-medium">{plan.headline}</p>
              {plan.prepared_fields?.length > 0 && (
                <dl className="mt-3 grid grid-cols-1 gap-x-8 gap-y-2.5 sm:grid-cols-2">
                  {plan.prepared_fields.map((f, i) => (
                    <div key={i} className="flex flex-col">
                      <dt className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">{f.label}</dt>
                      <dd className="text-sm">{f.value ? f.value : <span className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">— to confirm</span>}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </div>
            {plan.compliance_checks?.length > 0 && (
              <div className="rounded-xl border border-border bg-card p-4">
                <div className="flex items-center gap-2 text-sm font-medium"><ShieldCheck className="h-4 w-4 text-primary" /> Preparation checks · requires human review</div>
                <ul className="mt-3 space-y-2.5">
                  {plan.compliance_checks.map((c, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <ComplianceBadge status={c.status} />
                      <div><span className="text-sm font-medium">{c.item}</span>{c.note && <p className="text-xs text-muted-foreground">{c.note}</p>}</div>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div className="grid gap-3">
              {plan.draft_client_message && <CopyCard title="Draft message to client" text={plan.draft_client_message} />}
              {plan.draft_advisor_followup && <CopyCard title="Advisor follow-up" text={plan.draft_advisor_followup} />}
            </div>
            <div className="flex flex-wrap items-center gap-3 pt-1">
              {approved ? (
                <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-700">
                  <CheckCircle2 className="h-4 w-4" /> Approval recorded. No money moved or message was sent.
                </div>
              ) : (
                <Button onClick={approve} disabled={approving} className="px-5">{approving ? "Approving…" : "Approve reviewed packet"}</Button>
              )}
              <span className="text-xs text-muted-foreground">You approve; the agent did the prep. Nothing is executed.</span>
            </div>
            {plan.note && <p className="text-xs text-muted-foreground">{plan.note}</p>}
          </>
        )}
      </div>
    </div>
  );
}
