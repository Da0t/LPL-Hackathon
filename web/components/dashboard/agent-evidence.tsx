"use client";
import { useSyncExternalStore } from "react";
import { readRun, subscribeRuns, runKey } from "@/lib/agent-runs";
export function AgentEvidence({
  caseId,
  operation,
}: {
  caseId: string;
  operation: string;
}) {
  const key = runKey(caseId, operation);
  const run = useSyncExternalStore(
    subscribeRuns,
    () => readRun(key),
    () => undefined,
  );
  if (!run) return null;
  const models =
    run.diagnostics?.models ||
    Array.from(
      new Set(
        run.events.filter((e) => e.type === "model_start").map((e) => e.model),
      ),
    );
  const tools =
    run.diagnostics?.tools ||
    Array.from(
      new Set(run.events.filter((e) => e.type === "tool").map((e) => e.tool)),
    );
  const sources =
    run.diagnostics?.facts_cited ||
    Array.from(
      new Set(
        run.events.filter((e) => e.type === "source").map((e) => e.source_id),
      ),
    );
  const gated =
    ["plan", "reply-draft"].includes(operation) && run.auditVerdict !== "pass";
  const stage = run.events.filter((e) => e.type === "stage").at(-1)?.agent;
  return (
    <section
      className="my-4 rounded-xl border border-slate-300 bg-slate-50 p-4 text-slate-800"
      aria-label="Agent evidence and live activity"
    >
      <div className="flex flex-wrap justify-between gap-2">
        <strong className="text-sm">
          {run.running ? `${stage || "Agent"} · live activity` : "Run evidence"}
        </strong>
        <span className="text-xs">{run.running ? "Working" : "Complete"}</span>
      </div>
      <dl className="mt-2 space-y-1 break-words text-xs">
        <div>
          <dt className="inline font-semibold">Model: </dt>
          <dd className="inline">
            {models.length
              ? models.join(", ")
              : "No model call in this run (cached or offline)"}
          </dd>
        </div>
        <div>
          <dt className="inline font-semibold">Tools used: </dt>
          <dd className="inline">{tools.join(", ") || "None reported yet"}</dd>
        </div>
        <div>
          <dt className="inline font-semibold">Facts / sources cited: </dt>
          <dd className="inline">{sources.join(", ") || "None reported"}</dd>
        </div>
        <div>
          <dt className="inline font-semibold">Confidence: </dt>
          <dd className="inline">
            Not numerically calibrated. Check evidence coverage and the verifier
            verdict.
          </dd>
        </div>
        {run.diagnostics && (
          <div>
            {run.diagnostics.output_tokens} output tokens ·{" "}
            {(run.diagnostics.elapsed_ms / 1000).toFixed(1)} seconds
          </div>
        )}
      </dl>
      {run.error && (
        <p className="mt-2 text-sm text-red-700" role="alert">
          {run.error}
        </p>
      )}
      {gated ? (
        <p className="mt-3 text-xs">
          {run.tokenChunks || 0} output chunks received. Draft content is
          withheld until the record audit passes.
        </p>
      ) : (
        <details className="mt-3">
          <summary className="cursor-pointer text-xs font-medium">
            Live model output · unverified generation
          </summary>
          <p className="mt-2 text-xs">
            These are actual output deltas, not hidden reasoning. Treat partial
            output as unverified. The action packet is withheld until its audit
            passes.
          </p>
          <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap break-all rounded bg-white p-3 text-xs">
            {run.preview ||
              "Waiting for output. Cached and offline responses do not simulate a stream."}
          </pre>
        </details>
      )}
    </section>
  );
}
export function AuditVerdict({ audit }: { audit: any }) {
  if (!audit)
    return (
      <p className="my-3 rounded border border-amber-300 bg-amber-50 p-3 text-sm">
        Independent audit has not completed. Approval is unavailable.
      </p>
    );
  const pass = audit.verdict === "pass";
  return (
    <section
      className={`my-3 rounded-xl border p-4 text-sm ${pass ? "border-emerald-300 bg-emerald-50 text-emerald-900" : "border-amber-300 bg-amber-50 text-amber-900"}`}
      aria-label="Independent record audit"
    >
      <strong>Verifier: {pass ? "pass" : "needs fix"}</strong>
      <p className="mt-1">
        {audit.mode} · {audit.matched_fields}/{audit.checked_fields} filled
        fields match their recorded sources.
      </p>
      {audit.findings?.length > 0 && (
        <ul className="mt-2 space-y-2">
          {audit.findings.map((f: any, i: number) => (
            <li key={i}>
              <strong>{f.location}</strong>: {f.quote && <>“{f.quote}” — </>}
              {f.issue}
            </li>
          ))}
        </ul>
      )}
      <p className="mt-2 text-xs">
        No detected mismatch is not a guarantee or a compliance certification. A
        person still reviews the request.
      </p>
    </section>
  );
}
export function ComplianceSources({ review }: { review: any }) {
  if (!review?.retrieval) return null;
  return (
    <section
      className="my-3 rounded-xl border border-slate-300 bg-slate-50 p-4 text-sm"
      aria-label="Retrieved compliance guidance"
    >
      <strong>Sentinel · cited guidance</strong>
      <p className="mt-1">{review.retrieval.message}</p>
      {(review.citations || []).map((c: any) => (
        <details key={c.id} className="mt-3">
          <summary className="cursor-pointer">
            {c.id} · {c.title}
          </summary>
          <blockquote className="my-2 border-l-2 border-blue-500 pl-3">
            {c.quote}
          </blockquote>
          <a
            className="text-blue-800 underline"
            href={c.url}
            target="_blank"
            rel="noreferrer"
          >
            Open source
          </a>
          <p className="mt-1 text-xs">
            {c.authority} · Reviewed {c.reviewed_at}. Retrieval relevance is not
            confidence or a suitability determination.
          </p>
        </details>
      ))}
    </section>
  );
}
