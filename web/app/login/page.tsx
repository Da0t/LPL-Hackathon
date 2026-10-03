"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { ArrowRight } from "lucide-react";
import { BrandLogo } from "@/components/brand-logo";
import { CoherentMark } from "@/components/coherent-logo";
import RoutingBoard from "@/components/routing-board";
import { portalApi } from "@/lib/portal";
import "../workspace/portal.css";

type DevUser = { email: string; display_name: string; role: string };

const ease = [0.2, 0.7, 0.2, 1] as const;
const rise = {
  hidden: { opacity: 0, y: 14 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease } },
};

export default function Login() {
  const [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [devUsers, setDevUsers] = useState<DevUser[]>([]);
  const router = useRouter();
  const reduce = useReducedMotion();

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

  const container = {
    hidden: {},
    visible: { transition: { staggerChildren: reduce ? 0 : 0.07, delayChildren: reduce ? 0 : 0.1 } },
  };

  return (
    <main className="portal login-page">
      <section className="login-story">
        <Link href="/" aria-label="Coherent home">
          <BrandLogo height={34} />
        </Link>
        <motion.div initial={reduce ? false : "hidden"} animate="visible" variants={container}>
          <motion.h1 variants={rise}>Every request reaches the right advisor.</motion.h1>
          <motion.div variants={rise} className="login-board">
            <RoutingBoard />
          </motion.div>
          <motion.p variants={rise} className="login-caption">
            Matched on specialty and availability. A staff member confirms every assignment.
          </motion.p>
        </motion.div>
        <small>Coherent · LPL hackathon · Fictional records only</small>
      </section>

      <section className="login-form-area">
        <motion.form
          initial={reduce ? false : "hidden"}
          animate="visible"
          variants={container}
          onSubmit={(e) => {
            e.preventDefault();
            signIn(email, password);
          }}
        >
          <motion.div variants={rise} className="login-mark" aria-hidden>
            <CoherentMark size={36} />
          </motion.div>
          <motion.h2 variants={rise}>Welcome back.</motion.h2>
          <motion.p variants={rise}>Sign in to your Coherent workspace.</motion.p>
          <motion.label variants={rise}>
            Email address
            <input
              type="email"
              required
              autoComplete="username"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </motion.label>
          <motion.label variants={rise}>
            Password
            <input
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </motion.label>
          {error && (
            <p className="portal-error" role="alert">
              {error}
            </p>
          )}
          <motion.button variants={rise} className="portal-primary" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
            <ArrowRight size={18} />
          </motion.button>
          {devUsers.length > 0 && (
            <motion.div
              initial={reduce ? false : { opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, ease }}
              className="dev-login"
            >
              <span>Development sign-in, no password</span>
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
            </motion.div>
          )}
          <motion.p variants={rise} className="login-footnote">
            Access is provided by your advisor’s team.
            <br />
            Contact your administrator if you need help signing in.
          </motion.p>
        </motion.form>
      </section>
    </main>
  );
}
