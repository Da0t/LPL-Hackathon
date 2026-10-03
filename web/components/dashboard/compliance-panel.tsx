"use client";

import React, { useState } from "react";
import { ShieldCheck, RefreshCw } from "lucide-react";
import { complianceReview, ApiError, type ComplianceReview } from "@/lib/api";
import { AgentEvidence, ComplianceSources } from "./agent-evidence";
import { Section } from "./section";
import { agentNote, flagLabel } from "./labels";

const ITEMS = [
  { id: "identity_confirmed", label: "Client identity confirmed" },
  { id: "no_advice", label: "No investment / tax advice given" },
  { id: "suitability", label: "Suitability considered" },
  { id: "account_confirmed", label: "Account confirmed with the client" },
];

export function CompliancePanel({ detail, hc }: { detail: any; hc: any }) {
  const [checked, setChecked] = useState<boolean[]>(ITEMS.map(() => false));
  const [review, setReview] = useState<ComplianceReview | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const flags: string[] = detail.flags || [];
  const complianceFlags = flags.filter((f) => ["client_term_did_not_match_account_type", "possible_unauthorized_access"].includes(f));

  const run = async () => {
    setRunning(true); setError(null);
    try { setReview(await complianceReview(detail.case_id)); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Could not run the compliance review."); }
    finally { setRunning(false); }
  };

  return (
    <Section title="Compliance">
      <AgentEvidence caseId={detail.case_id} operation="compliance-review" />
      <ComplianceSources review={review} />
      <div className="rounded-2xl border border-border bg-card p-4">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-sm font-medium"><ShieldCheck className="h-4 w-4 text-primary" /> Advisor checklist</div>
          <button onClick={run} disabled={running}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground disabled:opacity-50">
            <RefreshCw className={`h-3 w-3 ${running ? "animate-spin" : ""}`} />
            {running ? "Reviewing…" : review ? "Re-run review" : "Run review"}
          </button>
        </div>
        <ul className="mt-3 space-y-2.5">
          {ITEMS.map((item, i) => {
            const result = review?.checks.find((c) => c.id === item.id);
            return (
              <li key={item.id}>
                <label className="flex cursor-pointer items-center gap-2 text-sm">
                  <input type="checkbox" checked={checked[i]} onChange={() => setChecked((c) => c.map((v, j) => (j === i ? !v : v)))}
                    className="h-4 w-4 accent-[#1677ff]" />
                  <span className={checked[i] ? "text-muted-foreground line-through" : ""}>{item.label}</span>
                  {result && (
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      result.status === "pass" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>
                      {result.status === "pass" ? "Reviewer: pass" : "Reviewer: needs attention"}
                    </span>
                  )}
                </label>
                {result && <p className="ml-6 mt-0.5 text-xs text-muted-foreground">{result.evidence}{!!result.citation_ids?.length && <span className="block mt-1 font-medium">Guidance: {result.citation_ids.join(", ")}. Expand the source excerpts above.</span>}</p>}
              </li>
            );
          })}
        </ul>
        {error && <p className="mt-3 text-xs text-red-600">{error}</p>}
        {review?.note && <p className="mt-3 text-xs text-muted-foreground">{agentNote(review.ai_mode, review.note)}</p>}
        {complianceFlags.length > 0 && (
          <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-xs text-amber-800">
            To resolve: {complianceFlags.map(flagLabel).join("; ")}.
          </div>
        )}
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-border pt-3 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <span className={`h-1.5 w-1.5 rounded-full ${hc?.live_model ? "bg-emerald-500" : "bg-muted-foreground"}`} />
            AI model: {hc ? (hc.live_model ? "Amazon Bedrock (live)" : "sample mode, not connected") : "…"}
          </span>
          <span>Fictional data</span>
        </div>
      </div>
    </Section>
  );
}
