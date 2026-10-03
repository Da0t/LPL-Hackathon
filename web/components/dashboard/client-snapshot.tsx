"use client";

import React from "react";
import type { ClientSnapshot } from "@/lib/api";
import { Chip, Section } from "./section";
import { money, prettyDate, sentence, statusLabel } from "./labels";

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 text-sm font-medium">{children}</dd>
    </div>
  );
}

export function ClientSnapshotPanel({ snapshot, onOpenCase }: { snapshot: ClientSnapshot | null; onOpenCase: (id: string) => void }) {
  if (!snapshot) return <p className="mt-6 text-sm text-muted-foreground">Client details are unavailable right now.</p>;
  const { client, accounts, recent_events, other_cases, usual_advisor, assigned_advisor } = snapshot;
  return (
    <div>
      <Section title="About this client">
        <dl className="grid grid-cols-2 gap-4 rounded-2xl border border-border bg-card p-4 sm:grid-cols-4">
          <Fact label="Prefers to be contacted by">{client.preferred_contact_channel ? sentence(client.preferred_contact_channel) : "Not recorded"}</Fact>
          <Fact label="Prefers to meet by">{client.meeting_preference ? sentence(client.meeting_preference) : "Not recorded"}</Fact>
          <Fact label="Usual advisor">{usual_advisor?.display_name || "None yet"}</Fact>
          <Fact label="Handling this request">{assigned_advisor?.display_name || "Not assigned"}</Fact>
        </dl>
      </Section>

      <Section title={`Accounts (${accounts.length})`}>
        <ul className="divide-y divide-border rounded-2xl border border-border bg-card">
          {accounts.map((a) => (
            <li key={a.account_id} className="flex items-center justify-between gap-4 p-4">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium">{a.label}</span>
                  <span className="text-sm text-muted-foreground">{a.masked_identifier}</span>
                  {a.is_case_account && <Chip tone="green">This request</Chip>}
                </div>
                {a.familiar_label && <p className="text-xs text-muted-foreground">{a.familiar_label}</p>}
              </div>
              {typeof a.balance === "number" && (
                <div className="shrink-0 text-right">
                  <div className="text-sm font-medium tabular-nums">{money(a.balance)}</div>
                  {a.balance_as_of && <div className="text-xs text-muted-foreground">as of {prettyDate(a.balance_as_of)}</div>}
                </div>
              )}
            </li>
          ))}
          {accounts.length === 0 && <li className="p-4 text-sm text-muted-foreground">No accounts on record.</li>}
        </ul>
        <p className="mt-2 text-xs text-muted-foreground">Balances are snapshots for context, not amounts available to withdraw.</p>
      </Section>

      <Section title="Recent account activity">
        {recent_events.length === 0 ? <p className="text-sm text-muted-foreground">No activity on record.</p> : (
          <ul className="space-y-3">
            {recent_events.map((e) => (
              <li key={e.source_id} className="flex gap-4">
                <span className="w-24 shrink-0 text-xs text-muted-foreground">{prettyDate(e.date)}</span>
                <div className="min-w-0">
                  <p className={`text-sm font-medium ${e.type === "security_alert" ? "text-red-700" : ""}`}>{sentence(e.type)}</p>
                  <p className="text-sm text-muted-foreground">{e.summary}</p>
                  <p className="text-xs text-muted-foreground/70">{e.account_label} {e.masked_identifier}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Other requests from this client">
        {other_cases.length === 0 ? <p className="text-sm text-muted-foreground">No other requests.</p> : (
          <ul className="space-y-2">
            {other_cases.map((c) => (
              <li key={c.case_id}>
                <button onClick={() => onOpenCase(c.case_id)}
                  className="block w-full rounded-xl border border-border bg-card p-3 text-left transition-colors hover:border-primary/40">
                  <p className="text-sm">{c.confirmed_plain_language_request}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{statusLabel(c.status)}{c.priority?.reason ? ` · ${c.priority.reason}` : ""}</p>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  );
}
