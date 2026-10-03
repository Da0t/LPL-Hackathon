"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowRight, LockKeyhole } from "lucide-react";
import { BrandLogo } from "@/components/brand-logo";
import { portalApi } from "@/lib/portal";
import "../workspace/portal.css";
type DevUser = { email: string; display_name: string; role: string };
export default function Login() {
  const [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [devUsers, setDevUsers] = useState<DevUser[]>([]);
  const router = useRouter();
  const signIn = async (email: string, password: string) => {
    setBusy(true);
    setError("");
    try {
      await portalApi("/auth/login", "POST", { email, password });
      const me = await portalApi("/auth/me");
      router.replace(me.role === "staff" ? "/dashboard" : "/workspace");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  // Populated only when the backend runs with COHERENT_DEV_LOGIN=1.
  useEffect(() => {
    portalApi("/auth/dev-users")
      .then((r) => setDevUsers(r.users || []))
      .catch(() => {});
  }, []);
  return (
    <main className="portal login-page">
      <section className="login-story">
        <Link href="/">
          <BrandLogo height={34} />
        </Link>
        <div>
          <p className="portal-eyebrow">YOUR FINANCIAL LIFE, CONNECTED</p>
          <h1>
            A clearer view.
            <br />A better conversation.
          </h1>
          <p>
            Your accounts, your information, and the next steps that matter—all
            in one place.
          </p>
          <div className="login-art">
            <div>
              <span>Everything in context</span>
              <strong>Your financial picture</strong>
              <div className="art-bars">
                {[38, 52, 44, 66, 60, 79, 72, 96].map((h, i) => (
                  <i key={i} style={{ height: h }} />
                ))}
              </div>
            </div>
            <div className="art-note">
              <LockKeyhole size={20} /> Built around you.
            </div>
          </div>
        </div>
        <small>Coherent · LPL hackathon · Fictional records only</small>
      </section>
      <section className="login-form-area">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            signIn(email, password);
          }}
        >
          <div className="login-symbol">
            <LockKeyhole size={25} />
          </div>
          <h2>Welcome back.</h2>
          <p>Sign in to your Coherent workspace.</p>
          <label>
            Email address
            <input
              type="email"
              required
              autoComplete="username"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <label>
            Password
            <input
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          {error && (
            <p className="portal-error" role="alert">
              {error}
            </p>
          )}
          <button className="portal-primary" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
            <ArrowRight size={18} />
          </button>
          {devUsers.length > 0 && (
            <div className="dev-login">
              <span>Development sign-in · no password</span>
              {devUsers.map((u) => (
                <button
                  key={u.email}
                  type="button"
                  className="portal-secondary"
                  disabled={busy}
                  onClick={() => signIn(u.email, "dev")}
                >
                  {u.display_name}
                  <small>{u.role === "staff" ? "Advisor workspace" : "Client portal"}</small>
                </button>
              ))}
            </div>
          )}
          <p className="login-footnote">
            Access is provided by your advisor’s team.
            <br />
            Contact your administrator if you need help signing in.
          </p>
        </form>
      </section>
    </main>
  );
}
