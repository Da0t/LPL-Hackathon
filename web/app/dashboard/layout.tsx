"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { portalApi } from "@/lib/portal";
export default function StaffLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [ready, setReady] = useState(false);
  const router = useRouter();
  useEffect(() => {
    portalApi("/auth/me")
      .then((a) => {
        if (a.role === "staff") setReady(true);
        else router.replace("/workspace");
      })
      .catch(() => router.replace("/login"));
  }, [router]);
  return ready ? (
    <>
      {children}
      <button
        className="fixed right-5 bottom-4 z-50 rounded-md border bg-white px-3 py-2 text-xs text-slate-500 shadow-sm"
        onClick={async () => {
          await portalApi("/auth/logout", "POST");
          router.replace("/login");
        }}
      >
        Sign out of staff workspace
      </button>
    </>
  ) : (
    <p className="p-12 text-slate-500">Verifying staff access…</p>
  );
}
