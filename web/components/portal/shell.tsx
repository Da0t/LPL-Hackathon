"use client";
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  UserRound,
  WalletCards,
  FileText,
  LogOut,
  ArrowUpRight,
  ShieldCheck,
} from "lucide-react";
import { BrandLogo } from "@/components/brand-logo";
import { Client, portalApi } from "@/lib/portal";
import { getMyRequests } from "@/lib/api";
const Context = createContext<{
  client: Client;
  setClient: (c: Client) => void;
  /** How many of the client's requests have an advisor question waiting on them. */
  awaiting: number;
  refreshAwaiting: () => void;
} | null>(null);
export const useClient = () => useContext(Context)!;
export function PortalShell({ children }: { children: React.ReactNode }) {
  const [client, setClient] = useState<Client | null>(null),
    [error, setError] = useState(""),
    [awaiting, setAwaiting] = useState(0);
  const path = usePathname(),
    router = useRouter();
  const clientId = client?.client_id;
  const refreshAwaiting = useCallback(() => {
    if (!clientId) return;
    getMyRequests(clientId)
      .then((r) => setAwaiting(r.requests.filter((x) => x.awaiting_reply).length))
      .catch(() => {});
  }, [clientId]);
  useEffect(refreshAwaiting, [refreshAwaiting, path]);
  useEffect(() => {
    portalApi("/auth/me")
      .then((actor) => {
        if (actor.role === "staff") {
          router.replace("/dashboard");
          return;
        }
        return portalApi<Client>("/portal/me").then(setClient);
      })
      .catch((e) => setError(e.message));
  }, [router]);
  if (!client)
    return (
      <div className="portal loading-screen">
        <BrandLogo height={32} />
        <p role="status">{error || "Opening your workspace…"}</p>
        {error && <Link href="/login">Back to sign in</Link>}
      </div>
    );
  const items = [
    ["/workspace", "Overview", LayoutDashboard],
    ["/workspace/profile", "My profile", UserRound],
    ["/workspace/finances", "Financial picture", WalletCards],
    ["/workspace/requests", "My requests", FileText],
  ] as const;
  return (
    <Context.Provider value={{ client, setClient, awaiting, refreshAwaiting }}>
      <div className="portal portal-shell">
        <aside className="portal-sidebar">
          <Link href="/" className="portal-brand">
            <BrandLogo height={26} />
          </Link>
          <div className="workspace-label">PERSONAL WORKSPACE</div>
          <nav aria-label="Client workspace">
            {items.map(([url, label, Icon]) => (
              <Link
                key={url}
                href={url}
                className={
                  (url === "/workspace" ? path === url : path.startsWith(url))
                    ? "active"
                    : ""
                }
              >
                <Icon size={19} />
                {label}
                {url === "/workspace/requests" && awaiting > 0 && (
                  <span
                    className="nav-badge"
                    aria-label={`${awaiting} waiting for your answer`}
                  >
                    {awaiting}
                  </span>
                )}
              </Link>
            ))}
          </nav>
          <div className="sidebar-bottom">
            <div className="connected">
              <ShieldCheck size={17} />
              <span>
                Private client workspace
                <small>Synthetic data environment</small>
              </span>
            </div>
            <button
              onClick={async () => {
                await portalApi("/auth/logout", "POST");
                router.replace("/login");
              }}
            >
              <LogOut size={17} />
              Sign out
            </button>
          </div>
        </aside>
        <div className="portal-main">
          <header className="portal-topbar">
            <span>Good to have you here, {client.profile.preferred_name}.</span>
            <div className="profile-pill">
              <span className="avatar">
                {client.display_name
                  .split(" ")
                  .map((x) => x[0])
                  .join("")}
              </span>
              <span>
                {client.display_name}
                <small>Personal account</small>
              </span>
            </div>
          </header>
          <main
            className={
              path.endsWith("/new")
                ? "portal-content request-content"
                : "portal-content"
            }
          >
            {children}
          </main>
        </div>
      </div>
    </Context.Provider>
  );
}
export function PageHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="portal-heading">
      <div>
        <p className="portal-eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}
