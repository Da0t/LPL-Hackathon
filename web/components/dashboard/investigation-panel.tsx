"use client";

import React, { useCallback, useEffect, useState } from "react";
import { getInvestigation, ApiError, type Investigation } from "@/lib/api";
import { AgentCard, Subheading } from "./section";
import { prettyDate } from "./labels";

const RISK: Record<Investigation["risk_level"], { label: string; cls: string }> = {
  high: { label: "High risk", cls: "border-red-200 bg-red-50 text-red-700" },
  medium: { label: "Medium risk", cls: "border-amber-200 bg-amber-50 text-amber-800" },
  low: { label: "Low risk", cls: "border-emerald-200 bg-emerald-50 text-emerald-700" },
};

export function InvestigationPanel({ caseId }: { caseId: string }) {
  const [inv, setInv] = useState<Investigation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try { setInv(await getInvestigation(caseId)); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Could not run the security review."); }
    finally { setLoading(false); }
  }, [caseId]);
  useEffect(() => { load(); }, [load]);

  return (
    <AgentCard title="Security review" agent="Investigation agent" loading={loading} onRefresh={load} refreshLabel="Re-run">
      {loading && <p className="text-sm text-muted-foreground">Checking the account records…</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}
      {!loading && inv && (
        <div className="space-y-5">
          <div className={`rounded-lg border p-3 ${RISK[inv.risk_level].cls}`}>
            <p className="text-sm font-semibold">{RISK[inv.risk_level].label}</p>
            <ul className="mt-1.5 space-y-1">
              {inv.reasons.map((r, i) => <li key={i} className="text-sm">• {r}</li>)}
            </ul>
          </div>

          <div>
            <Subheading>Timeline from account records</Subheading>
            <ol className="mt-2 space-y-3 border-l border-border pl-4">
              {inv.timeline.map((t, i) => (
                <li key={i} className="relative">
                  <span className={`absolute -left-[21px] top-1.5 h-2 w-2 rounded-full ${t.highlight ? "bg-red-500" : "bg-muted-foreground/40"}`} />
                  <div className="flex flex-wrap items-baseline gap-x-2">
                    <span className={`text-sm font-medium ${t.highlight ? "text-red-700" : ""}`}>{t.label}</span>
                    <span className="text-xs text-muted-foreground">{prettyDate(t.date)}{t.account ? ` · ${t.account}` : ""}</span>
                  </div>
                  <p className="text-sm text-muted-foreground">{t.detail}</p>
                  <p className="text-xs text-muted-foreground/70">Source: {t.source_id}</p>
                </li>
              ))}
            </ol>
          </div>

          <div>
            <Subheading>Suggested protective steps</Subheading>
            <ol className="mt-2 list-decimal space-y-1.5 pl-5 text-sm">
              {inv.recommended_steps.map((s, i) => <li key={i}>{s}</li>)}
            </ol>
          </div>

          <p className="border-t border-primary/15 pt-3 text-xs text-muted-foreground">
            Suggestions for the specialist team. Nothing has been frozen, reversed, or sent.{inv.note ? ` ${inv.note}` : ""}
          </p>
        </div>
      )}
    </AgentCard>
  );
}
