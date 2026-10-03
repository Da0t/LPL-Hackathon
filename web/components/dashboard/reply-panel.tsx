"use client";

import React, { useState } from "react";
import { Sparkles, ShieldCheck, ShieldAlert, PenLine, RefreshCw, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  draftReply, complianceReview, ApiError,
  type AgentTraceStep, type ComplianceReview, type SentCompliance,
} from "@/lib/api";

const AGENT_LABELS: Record<AgentTraceStep["agent"], string> = { drafter: "Drafter", compliance: "Compliance reviewer" };

export function ReplyPanel({ caseId, busy, onSend, onClose }: {
  caseId: string; busy: boolean; onSend: (text: string, compliance: SentCompliance) => void; onClose: () => void;
}) {
  const [instruction, setInstruction] = useState("");
  const [working, setWorking] = useState<"draft" | "review" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [reviewedText, setReviewedText] = useState<string | null>(null);
  const [review, setReview] = useState<ComplianceReview | null>(null);
  const [trace, setTrace] = useState<AgentTraceStep[]>([]);
  const [note, setNote] = useState<string | null>(null);
  const [override, setOverride] = useState(false);

  const stale = reviewedText !== null && text.trim() !== reviewedText.trim();
  const flagged = review?.verdict === "needs_changes";
  const canSend = !!review && !stale && !!text.trim() && (!flagged || override) && !busy && !working;

  const runDraft = async () => {
    setWorking("draft"); setError(null); setOverride(false);
    try {
      const r = await draftReply(caseId, instruction.trim() || undefined);
      setText(r.draft); setReviewedText(r.draft); setReview(r.review); setTrace(r.trace); setNote(r.note);
    } catch (e) { setError(e instanceof ApiError ? e.message : "Could not draft a reply."); }
    finally { setWorking(null); }
  };

  const recheck = async () => {
    setWorking("review"); setError(null); setOverride(false);
    try {
      const r = await complianceReview(caseId, text);
      setReview(r); setReviewedText(text);
      setTrace((t) => [...t, {
        agent: "compliance", step: "review",
        summary: r.verdict === "pass" ? "Re-checked the advisor's edit: passed." : `Re-checked the advisor's edit: flagged ${r.findings.length} issue(s).`,
      }]);
    } catch (e) { setError(e instanceof ApiError ? e.message : "Could not re-check the draft."); }
    finally { setWorking(null); }
  };

  return (
    <div className="mt-3 overflow-hidden rounded-2xl border border-primary/30 bg-primary/[0.03]">
      <div className="flex items-center justify-between border-b border-primary/15 px-4 py-2.5">
        <div className="flex flex-wrap items-center gap-2">
          <Sparkles className="h-4 w-4 text-primary" />
          <span className="text-sm font-semibold">Client reply</span>
          <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">Drafter</span>
          <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">Compliance reviewer</span>
        </div>
        <button onClick={onClose} aria-label="Close" className="text-muted-foreground hover:text-foreground"><X className="h-4 w-4" /></button>
      </div>

      <div className="space-y-4 p-4">
        <div>
          <textarea value={instruction} onChange={(e) => setInstruction(e.target.value)} rows={2}
            placeholder="What do you need from the client? (optional) e.g. ‘Ask when they need the money.’"
            className="w-full rounded-lg border border-border bg-background p-2.5 text-sm outline-none focus:ring-2 focus:ring-primary/30" />
          <Button size="sm" className="mt-2" disabled={!!working} onClick={runDraft}>
            <PenLine className="mr-1 h-3.5 w-3.5" />
            {working === "draft" ? "Agents working…" : review ? "Redraft" : "Draft reply"}
          </Button>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        {review && (
          <>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Draft · edit before sending</p>
              <textarea value={text} onChange={(e) => setText(e.target.value)} rows={6}
                className="mt-1.5 w-full rounded-lg border border-border bg-background p-2.5 text-sm outline-none focus:ring-2 focus:ring-primary/30" />
            </div>

            {stale ? (
              <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-muted/40 p-3 text-sm">
                <span className="text-muted-foreground">Edited since the last compliance review.</span>
                <Button size="sm" variant="outline" disabled={!!working || !text.trim()} onClick={recheck}>
                  <RefreshCw className={`mr-1 h-3.5 w-3.5 ${working === "review" ? "animate-spin" : ""}`} />
                  {working === "review" ? "Checking…" : "Re-check"}
                </Button>
              </div>
            ) : flagged ? (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
                <div className="flex items-center gap-2 text-sm font-medium text-amber-800"><ShieldAlert className="h-4 w-4" /> Compliance: needs changes</div>
                <ul className="mt-2 space-y-2">
                  {review.findings.map((f, i) => (
                    <li key={i} className="text-sm text-amber-800">
                      {f.quote && <span className="font-medium">“{f.quote}”</span>} {f.issue}
                      {f.suggestion && <span className="block text-xs opacity-80">{f.suggestion}</span>}
                    </li>
                  ))}
                </ul>
                <label className="mt-3 flex cursor-pointer items-center gap-2 border-t border-amber-200 pt-3 text-xs text-amber-800">
                  <input type="checkbox" checked={override} onChange={() => setOverride((v) => !v)} className="h-3.5 w-3.5" />
                  Send anyway. The override is recorded on the case.
                </label>
              </div>
            ) : (
              <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm font-medium text-emerald-700">
                <ShieldCheck className="h-4 w-4" /> Compliance: passed
              </div>
            )}

            {trace.length > 0 && (
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Agent trace</p>
                <ol className="mt-1.5 space-y-1.5 border-l border-primary/20 pl-4">
                  {trace.map((t, i) => (
                    <li key={i} className="relative text-sm">
                      <span className="absolute -left-[21px] top-1.5 h-2 w-2 rounded-full bg-primary/50" />
                      <span className="font-medium">{AGENT_LABELS[t.agent] || t.agent}</span>
                      <span className="text-muted-foreground"> · {t.summary}</span>
                    </li>
                  ))}
                </ol>
              </div>
            )}

            <div className="flex flex-wrap items-center gap-2">
              <Button size="sm" disabled={!canSend}
                onClick={() => onSend(text.trim(), { verdict: review.verdict, override: flagged && override })}>
                {busy ? "Sending…" : "Send as clarification"}
              </Button>
              <span className="text-xs text-muted-foreground">Moves the case to ‘Awaiting client’.</span>
            </div>
            {note && <p className="text-xs text-muted-foreground">{note}</p>}
          </>
        )}
      </div>
    </div>
  );
}
