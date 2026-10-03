"use client";

import React from "react";

type Sugg = { id: string; label: string; account_id?: string };

export type GraphState = {
  transcript?: string;
  suggestions?: Sugg[];
  question?: string | null;
  candidateIntent?: string | null;
  selectedAccountId?: string | null;
  uncertainty?: string | null;
  confirmed?: boolean;
  caseId?: string | null;
  advisorName?: string | null;
  security?: boolean;
};

const INTENT: Record<string, string> = {
  discuss_possible_withdrawal: "Withdrawal",
  account_service: "Account service",
  review_account_access: "Security review",
  rollover_or_transfer: "Rollover / transfer",
  beneficiary_or_estate: "Beneficiary / estate",
  investment_planning: "Investment planning",
  retirement_income: "Retirement income",
};
const titleize = (s: string) => s.replace(/[_-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
const intentLabel = (i?: string | null) => (!i ? "Your goal" : INTENT[i] || titleize(i).slice(0, 24));
const truncate = (s: string, n: number) => { s = (s || "").trim(); return s.length > n ? s.slice(0, n - 1) + "…" : s; };
const fanY = (i: number, total: number) => {
  if (total <= 1) return 50;
  const spread = Math.min(34, 16 * (total - 1));
  return 50 - spread / 2 + (spread / (total - 1)) * i;
};

type Node = { id: string; kind: string; label: string; sub?: string; x: number; y: number; selected?: boolean; dim?: boolean; pulse?: boolean; done?: boolean };

export default function RoutingGraph(props: GraphState) {
  const security = !!props.security ||
    /sign-?in|unauthor|fraud|recognize|takeover|hack|stolen|scam/.test(((props.transcript || "") + " " + (props.uncertainty || "")).toLowerCase());
  const sugg = (props.suggestions || []).slice(0, 3);
  const nodes: Node[] = [];
  nodes.push({ id: "root", kind: "root", label: truncate(props.transcript || "", 40) || "Your words", sub: props.transcript ? (props.confirmed ? "confirmed" : "interpreting…") : "Start anywhere", x: 11, y: 50 });

  sugg.forEach((s, i) => {
    const sel = !!(props.selectedAccountId && s.account_id === props.selectedAccountId);
    nodes.push({ id: "opt-" + (s.id || s.account_id || i), kind: "option", label: truncate(s.label, 28), x: 39, y: fanY(i, sugg.length), selected: sel, dim: props.confirmed && !sel });
  });
  if (!sugg.length && (props.transcript || props.question)) {
    nodes.push({ id: "clarify", kind: "clarify", label: props.uncertainty ? "Needs a quick check" : "Understanding…", x: 39, y: 50, pulse: true });
  }

  const hasGoal = props.candidateIntent || props.selectedAccountId || security || props.confirmed;
  if (hasGoal) nodes.push({ id: "goal", kind: "goal", label: security ? "Security review" : intentLabel(props.candidateIntent), x: 68, y: 50 });
  if (hasGoal) nodes.push({
    id: "dest", kind: "dest", x: 89, y: 50, done: props.confirmed,
    dim: !props.selectedAccountId && !props.confirmed,
    label: security ? "Security specialist" : (props.advisorName || "Your advisor"),
    sub: props.confirmed ? (props.caseId ? "Case " + props.caseId : "Sent") : undefined,
  });

  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
  const selOpt = sugg.find((s) => props.selectedAccountId && s.account_id === props.selectedAccountId);
  const edges: [string, string, boolean][] = [];
  sugg.forEach((s) => edges.push(["root", "opt-" + (s.id || s.account_id), !!props.confirmed || (!!props.selectedAccountId && s.account_id === props.selectedAccountId)]));
  if (!sugg.length && byId["clarify"]) edges.push(["root", "clarify", false]);
  if (byId["goal"]) {
    const src = selOpt ? "opt-" + (selOpt.id || selOpt.account_id) : (sugg[0] ? "opt-" + (sugg[0].id || sugg[0].account_id) : (byId["clarify"] ? "clarify" : "root"));
    edges.push([src, "goal", !!props.confirmed || !!selOpt]);
  }
  if (byId["dest"] && byId["goal"]) edges.push(["goal", "dest", !!props.confirmed]);

  return (
    <div className="relative h-full w-full">
      <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none">
        {edges.map(([from, to, active], i) => {
          const a = byId[from], b = byId[to];
          if (!a || !b) return null;
          return (
            <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
              stroke={active ? "#2563eb" : "rgba(15,23,42,0.14)"}
              strokeWidth={active ? 1.6 : 1.1}
              style={{ vectorEffect: "non-scaling-stroke", filter: active ? "drop-shadow(0 0 3px rgba(37, 99, 235,0.5))" : undefined, transition: "stroke .3s" }} />
          );
        })}
      </svg>
      {nodes.map((n, i) => (
        <div
          key={n.id}
          className={[
            "rg-pop absolute flex items-center gap-2.5 rounded-xl border px-3 py-2",
            "bg-card shadow-sm",
            n.kind === "root" ? "border-border bg-background" : "border-border",
            n.selected || n.done ? "border-blue-500 shadow-[0_0_18px_rgba(37,99,235,0.25)]" : "",
            n.kind === "clarify" ? "border-amber-400/60" : "",
            n.dim ? "opacity-40" : "",
          ].join(" ")}
          style={{ left: `${n.x}%`, top: `${n.y}%`, transform: "translate(-50%,-50%)", animationDelay: `${n.id === "root" ? 0 : 100 + i * 80}ms` }}
        >
          <span className={[
            "h-1.5 w-1.5 flex-none rounded-full",
            n.selected || n.done ? "bg-blue-500 shadow-[0_0_10px_#2563eb]" : n.kind === "root" || n.kind === "goal" ? "bg-zinc-600" : n.kind === "clarify" ? "bg-amber-500" : "bg-zinc-400",
            n.pulse ? "animate-pulse" : "",
          ].join(" ")} />
          <span className="min-w-0 max-w-[170px]">
            <span className="block truncate text-[12.5px] font-medium text-foreground">{n.label}</span>
            {n.sub && <span className="block truncate text-[10.5px] text-muted-foreground">{n.sub}</span>}
          </span>
        </div>
      ))}
    </div>
  );
}
