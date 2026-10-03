"use client";

import React, { useCallback, useEffect, useState } from "react";
import { ReadAloudButton } from "@/components/portal/accessibility";
import { Button } from "@/components/ui/button";
import { getMyRequests, replyToRequest, ApiError, type MyRequest } from "@/lib/api";

const WHERE: Record<MyRequest["lifecycle"], string> = {
  new: "Received. We're finding the right person for you.",
  awaiting_client: "We need an answer from you.",
  assigned: "With an advisor.",
  scheduled: "Your team recorded a meeting plan. Check the details with them.",
  resolved: "Done.",
};

function when(iso: string) {
  const d = new Date(iso);
  return isNaN(d.getTime()) ? "" : d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/** The client's earlier requests, with any question their advisor has sent and a box to answer it. */
export function MyRequests({ clientId }: { clientId: string }) {
  const [requests, setRequests] = useState<MyRequest[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [sending, setSending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    getMyRequests(clientId).then((r) => {setRequests(r.requests);setError(null);}).catch(()=>setError("We could not update your request status. Choose Refresh to try again."));
  }, [clientId]);
  useEffect(() => { setRequests([]); setError(null); load(); }, [load]);

  useEffect(()=>{const timer=setInterval(()=>{if(document.visibilityState==="visible")load();},15000);return()=>clearInterval(timer);},[load]);

  const send = async (caseId: string) => {
    setSending(caseId); setError(null);
    try {
      await replyToRequest(clientId, caseId, drafts[caseId] || "");
      setDrafts((d) => ({ ...d, [caseId]: "" }));
      load();
    } catch (e) { setError(e instanceof ApiError ? e.message : "Your answer did not send. Please try again."); }
    finally { setSending(null); }
  };

  if (requests.length === 0 && !error) return null;
  return (
    <section className="pb-12">
      <div className="request-followup-heading"><h2 className="text-2xl font-semibold tracking-tight">What happens next</h2><button className="portal-secondary" onClick={load}>Refresh status</button></div>
      <p>Your request asks for a conversation. No money has moved and no transaction has been approved.</p>
      {error && <p role="alert" className="mt-3 text-sm text-red-400">{error}</p>}
      <ul className="mt-4 space-y-4">
        {requests.map((r) => (
          <li key={r.case_id} className={`rounded-2xl border bg-card/60 p-6 ${r.awaiting_reply ? "border-primary" : "border-border"}`}>
            <p className="text-base">{r.request}</p>
            <p className={`mt-2 text-sm ${r.awaiting_reply ? "font-medium text-primary" : "text-muted-foreground"}`}>
              {WHERE[r.lifecycle]} <span className="text-muted-foreground">Sent {when(r.created_at)}.</span>
            </p>
            <ReadAloudButton text={[r.request,WHERE[r.lifecycle],...r.messages.map(m=>`${m.from==="client"?"You said":"Your team asks"}: ${m.text}`)].join(". ")} label="Read request and messages" />
            {r.messages.length > 0 && (
              <ul className="mt-4 space-y-3 border-t border-border pt-4">
                {r.messages.map((m, i) => (
                  <li key={i} className={`max-w-xl rounded-xl px-4 py-3 text-base ${m.from === "client" ? "ml-auto bg-primary/15" : "bg-foreground/5"}`}>
                    <p className="text-xs font-medium text-muted-foreground">{m.from === "client" ? "You" : "Your advisor"} · {when(m.at)}</p>
                    <p className="mt-1">{m.text}</p>
                  </li>
                ))}
              </ul>
            )}
            {r.awaiting_reply && (
              <div className="mt-4">
                <label htmlFor={`reply-${r.case_id}`} className="text-sm font-medium">Your answer</label>
                <textarea id={`reply-${r.case_id}`} rows={2} value={drafts[r.case_id] || ""}
                  onChange={(e) => setDrafts((d) => ({ ...d, [r.case_id]: e.target.value }))}
                  placeholder="Answer in your own words."
                  className="mt-2 w-full rounded-md border border-border bg-background p-3 text-base text-foreground outline-none focus:ring-2 focus:ring-primary/40" />
                <Button className="mt-3" disabled={sending === r.case_id || !(drafts[r.case_id] || "").trim()} onClick={() => send(r.case_id)}>
                  {sending === r.case_id ? "Sending…" : "Send answer"}
                </Button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
