import React from "react";
import { RefreshCw, Sparkles } from "lucide-react";

export function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-6">
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      <div className="mt-2">{children}</div>
    </div>
  );
}

export function Chip({ children, tone = "muted" }: { children: React.ReactNode; tone?: "muted" | "red" | "amber" | "green" }) {
  const tones = {
    muted: "bg-muted text-muted-foreground border-border",
    red: "bg-red-50 text-red-700 border-red-200",
    amber: "bg-amber-50 text-amber-800 border-amber-200",
    green: "bg-emerald-50 text-emerald-700 border-emerald-200",
  };
  return <span className={`whitespace-nowrap rounded-md border px-2 py-0.5 text-xs ${tones[tone]}`}>{children}</span>;
}

/** The framed card every agent's output sits in, so AI-prepared content is recognisable at a glance. */
export function AgentCard({ title, agent, loading, onRefresh, refreshLabel = "Regenerate", children }: {
  title: string; agent: string; loading?: boolean; onRefresh?: () => void; refreshLabel?: string; children: React.ReactNode;
}) {
  return (
    <div className="overflow-hidden rounded-xl border border-primary/30 bg-primary/[0.03]">
      <div className="flex items-center justify-between gap-3 border-b border-primary/15 px-4 py-2.5">
        <div className="flex flex-wrap items-center gap-2">
          <Sparkles className="h-4 w-4 text-primary" />
          <span className="text-sm font-semibold">{title}</span>
          <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">{agent}</span>
        </div>
        {onRefresh && (
          <button onClick={onRefresh} disabled={loading}
            className="flex shrink-0 items-center gap-1 text-xs text-muted-foreground hover:text-foreground disabled:opacity-50">
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} /> {loading ? "Working…" : refreshLabel}
          </button>
        )}
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

export function Subheading({ children }: { children: React.ReactNode }) {
  return <p className="text-xs font-semibold text-muted-foreground">{children}</p>;
}
