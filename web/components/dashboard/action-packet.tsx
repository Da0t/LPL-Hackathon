"use client";

// The fulfillment agent's prepared reply: what it found on the request, what is still missing,
// the checks the advisor has to make, and the message to the client, ready to edit and send.
import React, { useEffect, useState } from "react";
import { CheckCircle2, RefreshCw, AlertTriangle, Send, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { ActionPlan } from "@/lib/api";
import { Subheading } from "./section";
import { agentNote, timeAgo } from "./labels";

type SentEvent = { at: string; details?: { text?: string; acknowledged_flags?: string[] } };

function Shell({ title, aside, children }: { title: string; aside?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="mt-5 overflow-hidden rounded-2xl border border-primary/30 bg-primary/[0.03]">
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
      {reviewed.length > 0 && <p className="text-xs text-muted-foreground">Checks you confirmed before sending: {reviewed.join(", ")}</p>}
      <p className="flex items-center gap-1.5 text-sm text-emerald-700">
        <CheckCircle2 className="h-4 w-4" /> Their answer will show up on this request. Use Message client to follow up.
      </p>
    </Shell>
  );
}

// `sent` is the approval event from the case history, so the sent state survives a reload.
// `onSend` resolves to the reason the send was refused, or null when the message went out.
export function ActionPacket({ plan, loading, onRegenerate, onSend, sent, resolved }: {
  plan: ActionPlan | null; loading: boolean; onRegenerate: () => void;
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
  const toConfirm = checks.map((c, i) => ({ ...c, i })).filter((c) => c.status !== "pass");
  const passed = checks.filter((c) => c.status === "pass");
  const open = toConfirm.filter((c) => !ticked.includes(c.i)).length;
  const message = text.trim();
  const edited = !!plan && message !== (plan.draft_client_message || "").trim();
  const actionTitle = (plan?.action_type || "").replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
  const live = plan?.ai_mode === "bedrock" && !plan.note;

  const toggle = (i: number) => setTicked((t) => (t.includes(i) ? t.filter((x) => x !== i) : [...t, i]));
  const send = async () => {
    if (sending) return;
    setSending(true); setError(null);
    try { setError(await onSend(message, toConfirm.map((c) => c.item))); }
    finally { setSending(false); }
  };

  return (
    <Shell title="Reply ready for your review" aside={
      <button onClick={onRegenerate} disabled={loading || sending} className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground disabled:opacity-50">
        <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} /> {loading ? "Preparing…" : "Regenerate"}
      </button>
    }>
      {loading && <p className="text-sm text-muted-foreground">Pulling the facts from the request, running the checks and drafting a reply to the client…</p>}
      {!loading && !plan && <p className="text-sm text-muted-foreground">A reply could not be prepared right now. Try Regenerate, or use Message client to write one.</p>}
      {!loading && plan && (
        <>
          <p className={`flex items-center gap-2 text-sm font-medium ${open ? "text-amber-700" : "text-emerald-700"}`}>
            {open ? <AlertTriangle className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />}
            {open ? `${open} ${open === 1 ? "thing" : "things"} to confirm before you can send` : "Ready to send"}
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
              <p className="text-xs font-semibold uppercase tracking-wide text-amber-800">Still needed from the client</p>
              <p className="mt-1 text-sm text-amber-900">{missing.map((f) => f.label).join(", ")}</p>
              <p className="mt-1 text-xs text-amber-800">Make sure the message below asks for {missing.length === 1 ? "it" : "them"}.</p>
            </div>
          )}

          {checks.length > 0 && (
            <div>
              <Subheading>Confirm before sending</Subheading>
              <ul className="mt-2 space-y-2">
                {toConfirm.map((c) => (
                  <li key={c.i}>
                    <label className={`flex cursor-pointer items-start gap-2.5 rounded-lg border p-3 text-sm ${c.status === "flag" ? "border-red-200 bg-red-50" : "border-border bg-card"}`}>
                      <input type="checkbox" checked={ticked.includes(c.i)} onChange={() => toggle(c.i)} className="mt-0.5 h-4 w-4 flex-none" />
                      <span>
                        <span className="font-medium">{c.item}</span>
                        {c.status === "flag" && <span className="ml-2 rounded bg-red-100 px-1.5 py-0.5 text-[11px] font-medium text-red-700">Flagged</span>}
                        {c.note && <span className="block text-xs text-muted-foreground">{c.note}</span>}
                      </span>
                    </label>
                  </li>
                ))}
              </ul>
              {toConfirm.length > 0 && <p className="mt-2 text-xs text-muted-foreground">Ticking a box records on the request that you confirmed it.</p>}
              {passed.length > 0 && (
                <div className="mt-2">
                  <button onClick={() => setShowPassed((v) => !v)} aria-expanded={showPassed} className="flex items-center gap-1.5 text-xs text-emerald-700 hover:underline">
                    <CheckCircle2 className="h-3.5 w-3.5" /> {passed.length} {passed.length === 1 ? "check" : "checks"} passed
                    <ChevronDown className={`h-3 w-3 transition-transform ${showPassed ? "rotate-180" : ""}`} />
                  </button>
                  {showPassed && (
                    <ul className="mt-1.5 space-y-1 pl-5 text-xs text-muted-foreground">
                      {passed.map((c, i) => <li key={i}><span className="font-medium text-foreground">{c.item}</span>{c.note ? `: ${c.note}` : ""}</li>)}
                    </ul>
                  )}
                </div>
              )}
            </div>
          )}

          <div>
            <div className="flex items-center justify-between">
              <Subheading>Message to the client</Subheading>
              {edited && <button onClick={() => setText(plan.draft_client_message || "")} className="text-xs text-muted-foreground hover:text-foreground">Undo my edits</button>}
            </div>
            <textarea value={text} onChange={(e) => setText(e.target.value)} rows={5} maxLength={2000} aria-label="Message to the client"
              className="mt-1.5 w-full rounded-lg border border-border bg-background p-2.5 text-sm outline-none focus:ring-2 focus:ring-primary/30" />
            <p className="mt-1 text-xs text-muted-foreground">Edit it freely. The compliance reviewer checks the final wording when you send.</p>
          </div>

          {plan.draft_advisor_followup && (
            <div>
              <Subheading>After you send</Subheading>
              <p className="mt-1.5 whitespace-pre-wrap text-sm">{plan.draft_advisor_followup}</p>
            </div>
          )}

          {error && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}

          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={send} disabled={sending || open > 0 || !message} className="px-5">
              <Send className="mr-1.5 h-4 w-4" />{sending ? "Sending…" : "Send to client"}
            </Button>
            <span className="text-xs text-muted-foreground">
              {open > 0 ? "Tick the items above to enable sending."
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
