// Static "pipeline" visual for the landing , shows a request flowing from plain
// words, through Amazon Bedrock, to a confirmed request and the right advisor.
import React from "react";

function Node({
  kind, label, sub, active,
}: { kind: string; label: string; sub?: string; active?: boolean }) {
  return (
    <div
      className={`relative rounded-xl border px-4 py-3 backdrop-blur-sm ${
        active
          ? "border-blue-500/50 bg-blue-500/5 shadow-[0_0_24px_-6px_rgba(37, 99, 235,0.5)]"
          : "border-border bg-card/60"
      }`}
    >
      <div className="flex items-center gap-2">
        <span className={`h-1.5 w-1.5 rounded-full ${active ? "bg-blue-500 shadow-[0_0_8px_rgba(37, 99, 235,0.9)]" : "bg-muted-foreground/60"}`} />
        <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{kind}</span>
      </div>
      <p className="mt-1 text-sm font-medium text-foreground">{label}</p>
      {sub && <p className="mt-0.5 text-xs text-muted-foreground">{sub}</p>}
    </div>
  );
}

function Connector() {
  return (
    <div className="ml-6 flex h-5 items-center">
      <span className="h-full w-px bg-gradient-to-b from-border to-blue-500/40" />
    </div>
  );
}

export default function PipelinePreview() {
  return (
    <div className="mx-auto w-full max-w-sm rounded-2xl border border-border bg-background/50 p-4 backdrop-blur-md lg:mx-0">
      <div className="mb-3 flex items-center justify-between px-1">
        <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Live routing</span>
        <span className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue-500 shadow-[0_0_8px_rgba(37, 99, 235,0.9)]" />
          Amazon Bedrock
        </span>
      </div>
      <Node kind="Client says" label={"“The Roth thing from my old job”"} />
      <Connector />
      <Node kind="Coherent understands" label="No Roth IRA on file" sub="Closest match: rollover IRA from a former employer" active />
      <Connector />
      <Node kind="Confirmed request" label="Discuss a $6,000 withdrawal" sub="Rollover IRA · ****4821 · client-confirmed" active />
      <Connector />
      <Node kind="Routed to" label="Jordan Lee , retirement advisor" sub="Specialty match · available" active />
    </div>
  );
}
