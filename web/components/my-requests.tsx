"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { FileText, Printer, X, MessageCircleQuestion } from "lucide-react";
import { getMyRequests, replyToRequest, ApiError, type MyRequest } from "@/lib/api";
import { RequestDocument, portalApi } from "@/lib/portal";
import { RequestPaper } from "@/components/portal/request-document";

const WHERE: Record<MyRequest["lifecycle"], { label: string; detail: string; tone: string }> = {
  awaiting_client: { label: "Needs your answer", detail: "Your advisor asked a question. Your request waits until you answer.", tone: "attention" },
  new: { label: "Received", detail: "We're finding the right person for you.", tone: "progress" },
  assigned: { label: "With an advisor", detail: "An advisor is working on your request.", tone: "progress" },
  scheduled: { label: "Conversation scheduled", detail: "Your conversation is scheduled.", tone: "progress" },
  resolved: { label: "Done", detail: "This request is complete.", tone: "done" },
};

function when(iso: string) {
  const d = new Date(iso);
  return isNaN(d.getTime()) ? "" : d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/** One request as the client sees it: where it stands, the conversation, and the document they sent. */
type Row = { case_id: string; created_at: string; text: string; thread: MyRequest | null; document: RequestDocument | null };

function merge(threads: MyRequest[], documents: RequestDocument[]): Row[] {
  const byCase = new Map(documents.filter((d) => d.case_id).map((d) => [d.case_id as string, d]));
  const rows: Row[] = threads.map((t) => ({
    case_id: t.case_id, created_at: t.created_at, text: t.request, thread: t, document: byCase.get(t.case_id) || null,
  }));
  const seen = new Set(threads.map((t) => t.case_id));
  for (const d of documents)
    if (d.case_id && !seen.has(d.case_id))
      rows.push({ case_id: d.case_id, created_at: d.created_at, text: d.request_description, thread: null, document: d });
  const waiting = (r: Row) => (r.thread?.awaiting_reply ? 0 : 1);
  return rows.sort((a, b) => waiting(a) - waiting(b) || b.created_at.localeCompare(a.created_at));
}

/** Every request the client has sent, with any advisor question first and a box to answer it. */
export function MyRequests({ clientId, onChange }: { clientId: string; onChange?: () => void }) {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [sending, setSending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<RequestDocument | null>(null);

  const load = useCallback(async () => {
    const [threads, documents] = await Promise.allSettled([
      getMyRequests(clientId),
      portalApi<{ requests: RequestDocument[] }>("/portal/requests"),
    ]);
    if (threads.status === "rejected" && documents.status === "rejected")
      setError("Your requests could not be loaded. Refresh the page to try again.");
    setRows(merge(
      threads.status === "fulfilled" ? threads.value.requests : [],
      documents.status === "fulfilled" ? documents.value.requests : [],
    ));
  }, [clientId]);
  useEffect(() => { setRows(null); setError(null); load(); }, [load]);

  const send = async (caseId: string) => {
    setSending(caseId); setError(null);
    try {
      await replyToRequest(clientId, caseId, drafts[caseId] || "");
      setDrafts((d) => ({ ...d, [caseId]: "" }));
      await load();
      onChange?.();
    } catch (e) { setError(e instanceof ApiError ? e.message : "Your answer did not send. Please try again."); }
    finally { setSending(null); }
  };

  if (rows === null) return <p role="status">Loading your requests…</p>;
  if (rows.length === 0)
    return (
      <>
        {error && <p className="portal-error" role="alert">{error}</p>}
        <section className="portal-card empty-state">
          <FileText size={40} />
          <h2>You haven’t sent a request yet.</h2>
          <p>
            Describe an account question or a life change in your own words.
            <br />
            You’ll read the full document before anything is sent.
          </p>
          <Link className="portal-primary" href="/workspace/requests/new">Start a request</Link>
        </section>
      </>
    );

  const waiting = rows.filter((r) => r.thread?.awaiting_reply).length;
  return (
    <>
      {error && <p className="portal-error" role="alert">{error}</p>}
      {waiting > 0 && (
        <p className="request-summary">
          {waiting === 1 ? "1 request needs your answer." : `${waiting} requests need your answer.`}
        </p>
      )}
      <ul className="request-cards">
        {rows.map((r) => {
          const where = r.thread ? WHERE[r.thread.lifecycle] : null;
          const messages = r.thread?.messages || [];
          const draft = drafts[r.case_id] || "";
          return (
            <li key={r.case_id} className={`portal-card request-card${r.thread?.awaiting_reply ? " needs-answer" : ""}`}>
              <div className="request-card-top">
                <span className={`status-pill ${where?.tone || "progress"}`}>
                  {where?.tone === "attention" && <MessageCircleQuestion size={14} />}
                  {where?.label || r.document?.status || "Sent"}
                </span>
                <span>Sent {when(r.created_at)}</span>
              </div>
              <h2>{r.text}</h2>
              <p className="request-card-meta">
                {where && <>{where.detail} </>}
                <span>
                  Reference {r.case_id}
                  {r.document?.account ? `, about ${r.document.account.familiar_label}` : ""}
                </span>
              </p>
              {messages.length > 0 && (
                <ul className="request-thread" aria-label="Conversation with your advisor">
                  {messages.map((m, i) => (
                    <li key={i} className={m.from === "client" ? "mine" : ""}>
                      <small>{m.from === "client" ? "You" : "Your advisor"}, {when(m.at)}</small>
                      <p>{m.text}</p>
                    </li>
                  ))}
                </ul>
              )}
              {r.thread?.awaiting_reply && (
                <div className="request-reply">
                  <label htmlFor={`reply-${r.case_id}`}>Your answer</label>
                  <textarea id={`reply-${r.case_id}`} rows={3} maxLength={2000} value={draft}
                    onChange={(e) => setDrafts((d) => ({ ...d, [r.case_id]: e.target.value }))}
                    placeholder="Answer in your own words." />
                  <button className="portal-primary" disabled={sending === r.case_id || !draft.trim()} onClick={() => send(r.case_id)}>
                    {sending === r.case_id ? "Sending…" : "Send answer"}
                  </button>
                </div>
              )}
              {r.document && (
                <button className="request-card-document" onClick={() => setOpen(r.document)}>
                  <FileText size={16} />
                  View the document you sent
                </button>
              )}
            </li>
          );
        })}
      </ul>
      {open && <DocumentDialog document={open} onClose={() => setOpen(null)} />}
    </>
  );
}

function DocumentDialog({ document: doc, onClose }: { document: RequestDocument; onClose: () => void }) {
  const close = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const before = document.activeElement as HTMLElement | null;
    close.current?.focus();
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", key);
    return () => { window.removeEventListener("keydown", key); before?.focus(); };
  }, [onClose]);
  return (
    <div className="portal-modal-backdrop document-modal" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="document-view" role="dialog" aria-modal="true" aria-label={`Request document ${doc.case_id || ""}`}>
        <div className="document-toolbar">
          <button className="portal-secondary" onClick={() => window.print()}>
            <Printer size={16} />
            Print or save PDF
          </button>
          <button ref={close} className="icon-button" aria-label="Close document" onClick={onClose}>
            <X />
          </button>
        </div>
        <RequestPaper document={doc} />
      </div>
    </div>
  );
}
