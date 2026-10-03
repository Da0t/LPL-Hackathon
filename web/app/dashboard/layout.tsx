"use client";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { portalApi } from "@/lib/portal";
import { StaffContext, type StaffUser } from "@/components/dashboard/staff-context";

export default function StaffLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [user, setUser] = useState<StaffUser | null>(null);
  const router = useRouter();
  useEffect(() => {
    portalApi("/auth/me")
      .then((a) => {
        if (a.role === "staff") setUser({ displayName: a.display_name || "Staff", email: a.email || "" });
        else router.replace("/workspace");
      })
      .catch(() => router.replace("/login"));
  }, [router]);
  const signOut = useCallback(async () => {
    await portalApi("/auth/logout", "POST").catch(() => null);
    router.replace("/login");
  }, [router]);

  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center" role="status">
        <div className="flex items-center gap-3 text-sm text-muted-foreground">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-border border-t-primary" />
          Checking your staff access…
        </div>
      </div>
    );
  }
  return <StaffContext.Provider value={{ user, signOut }}>{children}</StaffContext.Provider>;
}
