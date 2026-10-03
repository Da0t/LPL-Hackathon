"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Plus, FileText, Printer, X } from "lucide-react";
import { PageHeading } from "@/components/portal/shell";
import { RequestDocument, portalApi, money } from "@/lib/portal";
import { RequestPaper } from "@/components/portal/request-document";
export default function Requests() {
  const [requests, setRequests] = useState<RequestDocument[]>([]),
    [selected, setSelected] = useState<RequestDocument | null>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true);
  useEffect(() => {
    portalApi("/portal/requests")
      .then((r) => setRequests(r.requests))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);
  return (
    <>
      <PageHeading
        eyebrow="MY REQUESTS"
        title="Keep the conversation moving."
        description="Your submitted requests, with the exact context you shared."
        action={
          <Link className="portal-primary" href="/workspace/requests/new">
            <Plus size={18} />
            New request
          </Link>
        }
      />
      {error && (
        <p className="portal-error" role="alert">
          {error}
        </p>
      )}
      {loading ? (
        <p role="status">Loading your requests…</p>
      ) : !requests.length ? (
        <section className="portal-card empty-state">
          <FileText size={40} />
          <h2>A clearer next step starts here.</h2>
          <p>
            Create a request to discuss an account, a life change, or a
            question.
            <br />
            You’ll review a complete document before it is sent.
          </p>
          <Link className="portal-primary" href="/workspace/requests/new">
            Create your first request
          </Link>
        </section>
      ) : (
        <div className="request-list">
          {requests.map((r) => (
            <button
              key={r.case_id}
              className="portal-card request-list-item"
              onClick={() => setSelected(r)}
            >
              <div>
                <span className="status-pill">{r.status}</span>
                <span>{r.created_at.slice(0, 10)}</span>
              </div>
              <h2>{r.request_description}</h2>
              <p>
                {r.account?.familiar_label || "Account to clarify"} ·{" "}
                {r.case_id}
              </p>
              <small>View saved document →</small>
            </button>
          ))}
        </div>
      )}
      {selected && (
        <div className="portal-modal-backdrop document-modal">
          <div className="document-view">
            <div className="document-toolbar">
              <button
                className="portal-secondary"
                onClick={() => window.print()}
              >
                <Printer size={16} />
                Print / Save PDF
              </button>
              <button
                className="icon-button"
                aria-label="Close document"
                onClick={() => setSelected(null)}
              >
                <X />
              </button>
            </div>
            <RequestPaper document={selected} />
          </div>
        </div>
      )}
    </>
  );
}
