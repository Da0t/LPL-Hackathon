"use client";

import React, { useCallback, useEffect, useState } from "react";
import { getNextSteps, ApiError, type NextSteps, type PlanStep } from "@/lib/api";
import { AgentCard } from "./section";
import { agentNote } from "./labels";

const OWNER: Record<PlanStep["owner"], { label: string; cls: string }> = {
  advisor: { label: "You", cls: "bg-primary/10 text-primary" },
  client: { label: "Client", cls: "bg-amber-100 text-amber-800" },
  operations: { label: "Operations", cls: "bg-muted text-muted-foreground" },
};

export function NextStepsPanel({ caseId }: { caseId: string }) {
  const [plan, setPlan] = useState<NextSteps | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<Record<number, boolean>>({});

  const load = useCallback(async () => {
    setLoading(true); setError(null); setDone({});
    try { setPlan(await getNextSteps(caseId)); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Could not prepare the plan."); }
    finally { setLoading(false); }
  }, [caseId]);
  useEffect(() => { load(); }, [load]);

  const finished = plan ? plan.steps.filter((_, i) => done[i]).length : 0;
  return (
    <AgentCard title="Next steps" agent="Planning agent" loading={loading} onRefresh={load}>
      {loading && <p className="text-sm text-muted-foreground">Working out what has to happen next…</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}
      {!loading && plan && (
        <div>
          <p className="text-sm font-medium">{plan.summary}</p>
          <ol className="mt-4 space-y-3">
            {plan.steps.map((step, i) => (
              <li key={i}>
                <label className="flex cursor-pointer items-start gap-3">
                  <input type="checkbox" checked={!!done[i]} onChange={() => setDone((d) => ({ ...d, [i]: !d[i] }))}
                    className="mt-1 h-4 w-4 flex-none accent-[#1677ff]" />
                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-center gap-2">
                      <span className={`text-sm font-medium ${done[i] ? "text-muted-foreground line-through" : ""}`}>{i + 1}. {step.title}</span>
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${OWNER[step.owner].cls}`}>{OWNER[step.owner].label}</span>
                    </span>
                    <span className="mt-0.5 block text-sm text-muted-foreground">{step.detail}</span>
                  </span>
                </label>
              </li>
            ))}
          </ol>
          <p className="mt-4 border-t border-primary/15 pt-3 text-xs text-muted-foreground">
            {finished} of {plan.steps.length} ticked off. Ticks are a working aid for this session and are not saved.
            {plan.note ? ` ${agentNote(plan.ai_mode, plan.note)}` : ""}
          </p>
        </div>
      )}
    </AgentCard>
  );
}
