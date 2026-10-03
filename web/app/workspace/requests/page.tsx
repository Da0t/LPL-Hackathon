"use client";
import Link from "next/link";
import { Plus } from "lucide-react";
import { MyRequests } from "@/components/my-requests";
import { PageHeading, useClient } from "@/components/portal/shell";
export default function Requests() {
  const { client, refreshAwaiting } = useClient();
  return (
    <>
      <PageHeading
        eyebrow="MY REQUESTS"
        title="Keep the conversation moving."
        description="Where each request stands, what your advisor has asked, and the document you sent."
        action={
          <Link className="portal-primary" href="/workspace/requests/new">
            <Plus size={18} />
            New request
          </Link>
        }
      />
      <MyRequests clientId={client.client_id} onChange={refreshAwaiting} />
    </>
  );
}
