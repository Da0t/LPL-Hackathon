"use client";

// The fulfillment agent's prepared reply: what it found on the request, what is still missing,
// the flagged items the advisor signs off, and the message to the client, ready to edit and send.
import React, { useEffect, useState } from "react";
import { CheckCircle2, RefreshCw, AlertTriangle, Send, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { AgentEvidence, AuditVerdict } from "./agent-evidence";
import type { ActionPlan } from "@/lib/api";
import { Subheading } from "./section";
import { agentNote, timeAgo } from "./labels";

type SentEvent = { at: string; details?: { text?: string; acknowledged_flags?: string[] } };

function Shell({ title, aside, children }: { title: string; aside?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="mt-5 overflow-hidden rounded-xl border border-primary/30 bg-primary/[0.03]">
      <div className="flex items-center justify-between gap-3 border-b border-primary/15 px-4 py-2.5">
        <span className="text-sm font-semibold">{title}</span>
        {aside}
      </div>
      <div className="space-y-5 p-4">{children}</div>
    </div>
  );
}

// What was actually sent, read from the case history, so it never drifts from what the client received.
function SentReceipt({ sent }: { sent: SentEvent }) {
  const reviewed = sent.details?.acknowledged_flags || [];
  return (
    <Shell title="Reply sent to the client" aside={<span className="text-xs text-muted-foreground">{timeAgo(sent.at)}</span>}>
      {sent.details?.text ? (
        <blockquote className="whitespace-pre-wrap rounded-lg border-l-2 border-emerald-500 bg-card p-3 text-sm">{sent.details.text}</blockquote>
      ) : (
        <p className="text-sm text-muted-foreground">The prepared action was approved without a message to the client.</p>
      )}
      {reviewed.length > 0 && <p className="text-xs text-muted-foreground">Flagged items you signed off before sending: {reviewed.join(", ")}</p>}
      <p className="flex items-center gap-1.5 text-sm text-emerald-700">
        <CheckCircle2 className="h-4 w-4" /> Their answer will show up on this request. Use Message client to follow up.
      </p>
    </Shell>
  );
}

// `sent` is the approval event from the case history, so the sent state survives a reload.
// `onSend` resolves to the reason the send was refused, or null when the message went out.
export function ActionPacket({ caseId, plan, loading, onRegenerate, onSend, sent, resolved }: {
  caseId: string; plan: ActionPlan | null; loading: boolean; onRegenerate: () => void;
  onSend: (message: string | undefined, reviewedChecks: string[]) => Promise<string | null>;
  sent: SentEvent | null; resolved: boolean;
}) {
  const [text, setText] = useState("");
  const [ticked, setTicked] = useState<number[]>([]);
  const [showPassed, setShowPassed] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { setText(plan?.draft_client_message || ""); setTicked([]); setError(null); }, [plan]);

  if (sent) return <SentReceipt sent={sent} />;
  if (resolved) return <Shell title="Prepared reply"><p className="text-sm text-muted-foreground">This request is resolved, so there is no reply to send.</p></Shell>;

  const fields = plan?.prepared_fields || [];
  const known = fields.filter((f) => f.value);
  const missing = fields.filter((f) => !f.value);
  const checks = plan?.compliance_checks || [];
  // A flag blocks the message until the advisor signs it; a review item is a reminder for acting on the request.
  const flagged = checks.map((c, i) => ({ ...c, i })).filter((c) => c.status === "flag");
  const reminders = checks.filter((c) => c.status === "review");
  const passed = checks.filter((c) => c.status === "pass");
  const open = flagged.filter((c) => !ticked.includes(c.i)).length;
  const message = text.trim();
  const edited = !!plan && message !== (plan.draft_client_message || "").trim();
  const actionTitle = (plan?.action_type || "").replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
  const live = plan?.ai_mode === "bedrock" && !plan.note;

  const toggle = (i: number) => setTicked((t) => (t.includes(i) ? t.filter((x) => x !== i) : [...t, i]));
  const send = async () => {
    if (sending) return;
    setSending(true); setError(null);
    try { setError(await onSend(message, flagged.map((c) => c.item))); }
    finally { setSending(false); }
  };

  return (
    <Shell title="Reply ready for your review" aside={
      <button onClick={onRegenerate} disabled={loading || sending} className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground disabled:opacity-50">
        <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} /> {loading ? "Preparing…" : "Regenerate"}
      </button>
    }>
      <AgentEvidence caseId={caseId} operation="plan" />
      {!loading && plan && <AuditVerdict audit={plan.audit} />}
      {!loading && plan && plan.audit?.verdict !== "pass" && <p>The prepared reply is withheld. Review the findings and regenerate.</p>}
      {loading && <p className="text-sm text-muted-foreground">Pulling the facts from the request, running the checks and drafting a reply to the client…</p>}
      {!loading && !plan && <p className="text-sm text-muted-foreground">A reply could not be prepared right now. Try Regenerate, or use Message client to write one.</p>}
      {!loading && plan && plan.audit?.verdict === "pass" && (
        <>
          <p className={`flex items-center gap-2 text-sm font-medium ${open ? "text-amber-700" : "text-emerald-700"}`}>
            {open ? <AlertTriangle className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />}
            {open ? `${open} flagged ${open === 1 ? "item needs" : "items need"} your sign-off before you can send` : "Ready to send"}
          </p>

          <div>
            <Subheading>The request</Subheading>
            <p className="mt-1.5 text-sm font-medium">{plan.headline || actionTitle}</p>
            {known.length > 0 && (
              <dl className="mt-2 grid grid-cols-1 gap-x-8 gap-y-2 sm:grid-cols-2">
                {known.map((f, i) => (
                  <div key={i}>
                    <dt className="text-xs text-muted-foreground">{f.label}</dt>
                    <dd className="text-sm">{f.value}</dd>
                  </div>
                ))}
              </dl>
            )}
          </div>

          {missing.length > 0 && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
              <p className="text-xs font-semibold text-amber-800">Still needed from the client</p>
              <p className="mt-1 text-sm text-amber-900">{missing.map((f) => f.label).join(", ")}</p>
              <p className="mt-1 text-xs text-amber-800">Make sure the message below asks for {missing.length === 1 ? "it" : "them"}.</p>
            </div>
          )}

          {flagged.length > 0 && (
            <div>
              <Subheading>Your sign-off</Subheading>
              <p className="mt-1 text-xs text-muted-foreground">Something on this request was flagged. Tick each statement that is true; it is recorded on the request under your name.</p>
              <ul className="mt-2 space-y-2">
                {flagged.map((c) => (
                  <li key={c.i}>
                    <label className="flex cursor-pointer items-start gap-2.5 rounded-lg border border-red-200 bg-red-50 p-3 text-sm">
                      <input type="checkbox" checked={ticked.includes(c.i)} onChange={() => toggle(c.i)} className="mt-0.5 h-4 w-4 flex-none" />
                      <span>
                        <span className="font-medium text-red-800">{c.confirm || `I have reviewed the flagged item: ${c.item}.`}</span>
                        <span className="block text-xs text-red-700">Why it was flagged: {c.note || c.item}</span>
                      </span>
                    </label>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div>
            <div className="flex items-center justify-between">
              <Subheading>Message to the client</Subheading>
              {edited && <button onClick={() => setText(plan.draft_client_message || "")} className="text-xs text-muted-foreground hover:text-foreground">Undo my edits</button>}
            </div>
            <textarea value={text} onChange={(e) => setText(e.target.value)} rows={5} maxLength={2000} aria-label="Message to the client"
              className="mt-1.5 w-full rounded-lg border border-border bg-background p-2.5 text-sm outline-none focus:ring-2 focus:ring-primary/30" />
            <p className="mt-1 text-xs text-muted-foreground">Edit it freely. The independent record auditor and compliance reviewer check the final wording when you send.</p>
          </div>

          {(plan.draft_advisor_followup || reminders.length > 0) && (
            <div>
              <Subheading>Before you act on the request</Subheading>
              {plan.draft_advisor_followup && <p className="mt-1.5 whitespace-pre-wrap text-sm">{plan.draft_advisor_followup}</p>}
              {reminders.length > 0 && (
                <ul className="mt-2 space-y-1.5">
                  {reminders.map((c, i) => (
                    <li key={i} className="flex gap-2 text-sm">
                      <span className="mt-2 h-1 w-1 flex-none rounded-full bg-primary" />
                      <span><span className="font-medium">{c.item}</span>{c.note ? `: ${c.note}` : ""}</span>
                    </li>
                  ))}
                </ul>
              )}
              <p className="mt-2 text-xs text-muted-foreground">Reminders only. They do not hold up the message.</p>
            </div>
          )}

          {passed.length > 0 && (
            <div>
              <button onClick={() => setShowPassed((v) => !v)} aria-expanded={showPassed} className="flex items-center gap-1.5 text-xs text-emerald-700 hover:underline">
                <CheckCircle2 className="h-3.5 w-3.5" /> {passed.length} automatic {passed.length === 1 ? "check" : "checks"} passed
                <ChevronDown className={`h-3 w-3 transition-transform ${showPassed ? "rotate-180" : ""}`} />
              </button>
              {showPassed && (
                <ul className="mt-1.5 space-y-1 pl-5 text-xs text-muted-foreground">
                  {passed.map((c, i) => <li key={i}><span className="font-medium text-foreground">{c.item}</span>{c.note ? `: ${c.note}` : ""}</li>)}
                </ul>
              )}
            </div>
          )}

          {error && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}

          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={send} disabled={sending || open > 0 || !message} className="px-5">
              <Send className="mr-1.5 h-4 w-4" />{sending ? "Sending…" : "Send to client"}
            </Button>
            <span className="text-xs text-muted-foreground">
              {open > 0 ? "Tick your sign-off above to enable sending."
                : !message ? "Write a message to send."
                : "Sends this message only. No money moves and no paperwork is submitted."}
            </span>
          </div>
          <p className="text-xs text-muted-foreground">{live ? "Prepared by the live AI model from this request's records." : agentNote(plan.ai_mode, plan.note)}</p>
        </>
      )}
    </Shell>
  );
}
