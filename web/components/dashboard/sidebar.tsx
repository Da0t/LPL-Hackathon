"use client";

// The workspace navigation: triage work for whoever is assigning, in-progress work for advisors, then the firm-wide views.
import React from "react";
import Link from "next/link";
import {
  Inbox, UserPlus, Flag, ShieldAlert, UserCheck, Hourglass, Columns3, BarChart3, Home, MessageSquarePlus, LogOut, X,
} from "lucide-react";
import { useStaff } from "./staff-context";

export type Filter = "all" | "assign" | "security" | "flagged" | "assigned" | "waiting";
export type View = "queue" | "pipeline" | "impact";

export const FILTER_LABELS: Record<Filter, string> = {
  all: "All requests", assign: "To assign", security: "Security", flagged: "Flagged", assigned: "Assigned", waiting: "Waiting on client",
};

const FILTER_ICONS: Record<Filter, React.ComponentType<{ className?: string }>> = {
  all: Inbox, assign: UserPlus, security: ShieldAlert, flagged: Flag, assigned: UserCheck, waiting: Hourglass,
};

const GROUPS: { title: string; items: Filter[] }[] = [
  { title: "Triage", items: ["assign", "security", "flagged"] },
  { title: "In progress", items: ["assigned", "waiting"] },
];

const itemClass = (active: boolean) =>
  `flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-2 text-sm outline-none transition-colors focus-visible:ring-2 focus-visible:ring-primary/40 ${
    active ? "bg-primary/10 font-medium text-primary" : "text-foreground/80 hover:bg-foreground/5 hover:text-foreground"}`;

function GroupTitle({ children }: { children: React.ReactNode }) {
  return <p className="px-2.5 pb-1 pt-5 text-xs font-medium text-muted-foreground">{children}</p>;
}

const initials = (name: string) => name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase()).join("") || "S";

export function Sidebar({ view, filter, counts, securityUrgent, liveModel, onFilter, onView, onClose }: {
  view: View; filter: Filter; counts: Record<Filter, number>;
  /** True while a security request still needs sending to the specialist team. */
  securityUrgent: boolean;
  /** Whether the live AI model is connected; undefined until the health check answers. */
  liveModel?: boolean;
  onFilter: (f: Filter) => void; onView: (v: View) => void;
  /** Present when the sidebar is shown as a drawer on a small screen. */
  onClose?: () => void;
}) {
  const staff = useStaff();
  const filterItem = (key: Filter) => {
    const Icon = FILTER_ICONS[key];
    const active = view === "queue" && filter === key;
    const n = counts[key];
    // Triage counts are work waiting on someone, so they stand out; the rest are just totals.
    const badge = key === "security" && securityUrgent ? "bg-red-100 font-semibold text-red-700"
      : key === "assign" && n > 0 ? "bg-primary/15 font-semibold text-primary"
      : "text-muted-foreground";
    return (
      <button key={key} onClick={() => onFilter(key)} aria-current={active ? "page" : undefined} className={itemClass(active)}>
        <span className="flex min-w-0 items-center gap-2.5"><Icon className="h-4 w-4 flex-none" /><span className="truncate">{FILTER_LABELS[key]}</span></span>
        <span className={`min-w-5 rounded-full px-1.5 py-0.5 text-center text-xs tabular-nums ${badge}`}>{n}</span>
      </button>
    );
  };

  return (
    <div className="flex h-full w-64 flex-col border-r border-border bg-[#f7f9fc]">
      <div className="flex items-center justify-between px-4 pt-4">
        <div className="flex items-center gap-2.5">
          <img src="/coherent-icon.png" alt="" className="h-7 w-7" />
          <div>
            <div className="text-sm font-semibold leading-tight">Coherent</div>
            <div className="text-xs text-muted-foreground">Staff workspace</div>
          </div>
        </div>
        {onClose && (
          <button onClick={onClose} aria-label="Close menu" className="rounded-md p-1.5 text-muted-foreground hover:bg-foreground/5 hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      <nav aria-label="Workspace" className="flex-1 overflow-y-auto px-2.5 pb-4 pt-4">
        {filterItem("all")}
        {GROUPS.map((g) => (
          <div key={g.title}>
            <GroupTitle>{g.title}</GroupTitle>
            <div className="space-y-0.5">{g.items.map(filterItem)}</div>
          </div>
        ))}
        <GroupTitle>Insights</GroupTitle>
        <div className="space-y-0.5">
          <button onClick={() => onView("pipeline")} aria-current={view === "pipeline" ? "page" : undefined} className={itemClass(view === "pipeline")}>
            <span className="flex items-center gap-2.5"><Columns3 className="h-4 w-4" /> Pipeline</span>
          </button>
          <button onClick={() => onView("impact")} aria-current={view === "impact" ? "page" : undefined} className={itemClass(view === "impact")}>
            <span className="flex items-center gap-2.5"><BarChart3 className="h-4 w-4" /> Impact</span>
          </button>
        </div>
      </nav>

      <div className="border-t border-border px-2.5 py-3">
        <Link href="/intake" className="flex items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-sm text-muted-foreground hover:bg-foreground/5 hover:text-foreground">
          <MessageSquarePlus className="h-4 w-4" /> Client intake
        </Link>
        <Link href="/" className="flex items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-sm text-muted-foreground hover:bg-foreground/5 hover:text-foreground">
          <Home className="h-4 w-4" /> Home
        </Link>
        <p className="flex items-center gap-2 px-2.5 pt-2 text-xs text-muted-foreground">
          <span className={`h-1.5 w-1.5 flex-none rounded-full ${liveModel ? "bg-emerald-500" : "bg-muted-foreground/50"}`} />
          {liveModel === undefined ? "Checking the AI model…" : liveModel ? "AI model connected" : "AI model in sample mode"}
        </p>
        <p className="px-2.5 pt-1 text-xs text-muted-foreground">Demo workspace. All clients and data are fictional.</p>
      </div>

      {staff && (
        <div className="flex items-center gap-2.5 border-t border-border px-4 py-3">
          <span className="flex h-8 w-8 flex-none items-center justify-center rounded-full bg-primary/15 text-xs font-semibold text-primary">
            {initials(staff.user.displayName)}
          </span>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium">{staff.user.displayName}</div>
            {staff.user.email && <div className="truncate text-xs text-muted-foreground">{staff.user.email}</div>}
          </div>
          <button onClick={staff.signOut} aria-label="Sign out" title="Sign out"
            className="rounded-md p-1.5 text-muted-foreground outline-none hover:bg-foreground/5 hover:text-foreground focus-visible:ring-2 focus-visible:ring-primary/40">
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
}
