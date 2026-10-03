"use client";

// The request queue: one row per request, most pressing first, each explaining why it sits where it does.
import React, { useEffect, useRef } from "react";
import { Search, UserCheck, X } from "lucide-react";
import { prettyCategory, type CaseRow } from "@/lib/api";
import { Chip } from "./section";
import { PRIORITY_DOT, PRIORITY_TEXT, statusLabel, timeAgo } from "./labels";

export type Sort = "priority" | "newest";

// Only the rows that need someone now carry a coloured edge, so the eye lands on them first.
const RAIL: Record<string, string> = { urgent: "before:bg-red-500", high: "before:bg-amber-500" };

const EMPTY: Record<string, string> = {
  all: "No requests yet. They appear here as soon as a client confirms one.",
  assign: "Nothing to assign. Every open request has someone handling it.",
  security: "No security concerns have been raised.",
  flagged: "No flagged requests.",
  assigned: "No requests are assigned yet.",
  waiting: "No requests are waiting on a client.",
};

function SkeletonRows() {
  return (
    <div aria-hidden className="animate-pulse">
      {[0, 1, 2, 3, 4].map((i) => (
        <div key={i} className="border-b border-border px-4 py-4">
          <div className="flex justify-between"><div className="h-3.5 w-32 rounded bg-muted" /><div className="h-3 w-10 rounded bg-muted" /></div>
          <div className="mt-3 h-3 w-full rounded bg-muted" />
          <div className="mt-2 h-3 w-2/3 rounded bg-muted" />
          <div className="mt-3 h-3 w-40 rounded bg-muted" />
        </div>
      ))}
    </div>
  );
}

export function QueueList({ title, filterKey, summary, cases, loading, error, onRetry, selectedId, onOpen, search, onSearch, sort, onSort }: {
  title: string; filterKey: string; summary: string; cases: CaseRow[]; loading: boolean; error: string | null; onRetry: () => void;
  selectedId: string | null; onOpen: (id: string) => void;
  search: string; onSearch: (q: string) => void; sort: Sort; onSort: (s: Sort) => void;
}) {
  const searchRef = useRef<HTMLInputElement>(null);
  // "/" jumps to search from anywhere in the workspace, unless the person is already typing.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (e.key !== "/" || e.metaKey || e.ctrlKey || e.altKey || el?.closest("input, textarea, select, [contenteditable]")) return;
      e.preventDefault(); searchRef.current?.focus();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const first = loading && cases.length === 0;
  return (
    <>
      <div className="border-b border-border px-4 pb-3 pt-4">
        <div className="flex items-baseline justify-between gap-3">
          <h1 className="text-lg font-semibold tracking-tight">{title}</h1>
          {!first && <span className="text-sm tabular-nums text-muted-foreground">{cases.length}</span>}
        </div>
        <p className="mt-0.5 text-sm text-muted-foreground">{first ? "Loading requests…" : summary}</p>
        <div className="mt-3 flex items-center gap-2">
          <div className="relative min-w-0 flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input ref={searchRef} value={search} onChange={(e) => onSearch(e.target.value)} placeholder="Search requests" aria-label="Search requests"
              onKeyDown={(e) => { if (e.key === "Escape") { onSearch(""); e.currentTarget.blur(); } }}
              className="h-9 w-full rounded-lg border border-border bg-background pl-9 pr-8 text-sm outline-none focus:border-primary/50 focus:ring-2 focus:ring-primary/25" />
            {search ? (
              <button onClick={() => onSearch("")} aria-label="Clear search" className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-muted-foreground hover:text-foreground">
                <X className="h-3.5 w-3.5" />
              </button>
            ) : (
              <kbd className="pointer-events-none absolute right-2.5 top-1/2 hidden -translate-y-1/2 rounded border border-border bg-muted px-1.5 text-xs text-muted-foreground sm:block">/</kbd>
            )}
          </div>
          <div className="flex h-9 flex-none rounded-lg border border-border p-0.5 text-xs" role="group" aria-label="Sort requests">
            {(["priority", "newest"] as Sort[]).map((s) => (
              <button key={s} onClick={() => onSort(s)} aria-pressed={sort === s}
                className={`rounded-md px-2.5 ${sort === s ? "bg-primary/10 font-medium text-primary" : "text-muted-foreground hover:text-foreground"}`}>
                {s === "priority" ? "Priority" : "Newest"}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {first && <SkeletonRows />}
        {error && (
          <div role="alert" className="m-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error} <button onClick={onRetry} className="font-medium underline underline-offset-2">Try again</button>
          </div>
        )}
        {!loading && !error && cases.length === 0 && (
          <div className="px-6 py-12 text-center text-sm text-muted-foreground">
            {search.trim() ? (
              <>
                <p>No requests match “{search.trim()}”.</p>
                <button onClick={() => onSearch("")} className="mt-2 font-medium text-primary hover:underline">Clear search</button>
              </>
            ) : <p>{EMPTY[filterKey] || "No requests here."}</p>}
          </div>
        )}
        <ul>
          {cases.map((c) => {
            const level = c.priority?.level || "normal";
            const selected = selectedId === c.case_id;
            const assigned = !!c.routing?.assigned_advisor_id;
            const unowned = c.lifecycle === "new" && !c.categories?.includes("fraud_or_security");
            return (
              <li key={c.case_id}>
                <button onClick={() => onOpen(c.case_id)} aria-current={selected ? "true" : undefined}
                  className={`relative block w-full border-b border-border py-3.5 pl-5 pr-4 text-left outline-none transition-colors before:absolute before:inset-y-0 before:left-0 before:w-1 focus-visible:bg-foreground/[0.04] ${
                    RAIL[level] || ""} ${selected ? "bg-primary/[0.07]" : "hover:bg-foreground/[0.03]"} ${level === "done" ? "opacity-70" : ""}`}>
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="truncate font-medium">{c.client_display_name}</span>
                    <span className="shrink-0 text-xs tabular-nums text-muted-foreground">{timeAgo(c.created_at)}</span>
                  </div>
                  <p className="mt-0.5 line-clamp-2 text-sm text-muted-foreground">{c.confirmed_plain_language_request}</p>
                  <div className="mt-2 flex items-center justify-between gap-3">
                    <p className={`flex min-w-0 items-center gap-2 text-xs font-medium ${PRIORITY_TEXT[level]}`}>
                      <span className={`h-2 w-2 flex-none rounded-full ${PRIORITY_DOT[level]}`} /><span className="truncate">{c.priority?.reason || statusLabel(c.status)}</span>
                    </p>
                    {assigned ? (
                      <span className="flex flex-none items-center gap-1 text-xs text-muted-foreground"><UserCheck className="h-3.5 w-3.5" />Assigned</span>
                    ) : unowned ? (
                      <span className="flex-none rounded-md border border-dashed border-primary/40 px-1.5 py-0.5 text-xs text-primary">Unassigned</span>
                    ) : null}
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    {(c.categories || []).slice(0, 2).map((cat) => (
                      <Chip key={cat} tone={cat === "fraud_or_security" ? "red" : "muted"}>{prettyCategory(cat)}</Chip>
                    ))}
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </>
  );
}
