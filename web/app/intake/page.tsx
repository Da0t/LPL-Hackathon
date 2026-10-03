"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import RoutingGraph, { type GraphState } from "@/components/routing-graph";
import {
  startIntake, intakeTurn, confirmIntake, getDemoClients,
  type TurnResponse, type Suggestion, ApiError,
} from "@/lib/api";
import { Mic, Loader2, ArrowRight, ArrowLeft, Check } from "lucide-react";

type Screen = "start" | "describe" | "review" | "success";

export default function IntakePage() {
  const [screen, setScreen] = useState<Screen>("start");
  const [clients, setClients] = useState<{ client_id: string; display_name: string }[]>([]);
  const [clientId, setClientId] = useState("CLIENT-017");
  const [clientName, setClientName] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);

  const [words, setWords] = useState("");
  const [turn, setTurn] = useState<TurnResponse | null>(null);
  const [selectedAccountId, setSelectedAccountId] = useState<string | null>(null);
  const [seen, setSeen] = useState<Record<string, Suggestion>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [summary, setSummary] = useState("");
  const [amount, setAmount] = useState("");
  const [caseId, setCaseId] = useState<string | null>(null);
  const [clientSummary, setClientSummary] = useState("");
  const [inputMode, setInputMode] = useState<"text" | "voice">("text");
  const [listening, setListening] = useState(false);

  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reqSeq = useRef(0);
  const recog = useRef<any>(null);

  useEffect(() => {
    getDemoClients().then((r) => setClients(r.clients)).catch(() => {});
  }, []);

  const graphState: GraphState = {
    transcript: turn?.transcript ?? words,
    suggestions: turn?.suggestions,
    question: turn?.question,
    candidateIntent: turn?.candidate_intent,
    selectedAccountId,
    uncertainty: turn?.uncertainty,
    confirmed: screen === "success",
    caseId,
  };

  const runTurn = useCallback(
    async (text: string, optionId: string | null, mode: "text" | "voice") => {
      if (!sessionId || !text.trim()) return;
      const seq = ++reqSeq.current;
      setBusy(true); setError(null);
      try {
        const data = await intakeTurn(sessionId, clientId, { text, input_mode: mode, selected_option_id: optionId });
        if (seq !== reqSeq.current) return;
        setTurn(data);
        setSeen((prev) => {
          const next = { ...prev };
          (data.suggestions || []).forEach((s) => { if (s.account_id) next[s.account_id] = s; });
          return next;
        });
        if (data.selected_account_id) setSelectedAccountId(data.selected_account_id);
      } catch (e) {
        if (seq === reqSeq.current) setError(e instanceof ApiError ? e.message : "Something went wrong.");
      } finally {
        if (seq === reqSeq.current) setBusy(false);
      }
    },
    [sessionId, clientId],
  );

  const schedule = (text: string) => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => runTurn(text, selectedAccountId, inputMode), 1200);
  };

  const begin = async () => {
    setBusy(true); setError(null);
    try {
      const d = await startIntake(clientId);
      setSessionId(d.session_id); setClientName(d.client_display_name);
      setScreen("describe");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not start. Is the backend running?");
    } finally { setBusy(false); }
  };

  const selectSuggestion = (s: Suggestion) => {
    setSelectedAccountId(s.account_id ?? null);
    runTurn(words, s.account_id ?? s.id, inputMode);
  };

  const toReview = () => {
    const accLabel = selectedAccountId && seen[selectedAccountId]?.label;
    const guess =
      selectedAccountId && turn?.candidate_intent === "discuss_possible_withdrawal"
        ? `I want to speak with an advisor about a possible withdrawal from my ${(accLabel || "retirement account").toLowerCase()}.`
        : words.trim();
    setSummary(guess);
    setScreen("review");
  };

  const confirm = async () => {
    if (!sessionId || !summary.trim()) { setError("Please describe the request in your own words."); return; }
    setBusy(true); setError(null);
    const amt = amount.trim() ? Number(amount.replace(/,/g, "")) : null;
    if (amount.trim() && (!Number.isFinite(amt) || (amt as number) <= 0)) { setError("Enter a positive amount, or leave it blank."); setBusy(false); return; }
    try {
      const d = await confirmIntake(sessionId, clientId, {
        confirmed_plain_language_request: summary.trim(),
        selected_account_id: selectedAccountId,
        amount_requested: amt,
      });
      setCaseId(d.case_id); setClientSummary(d.client_summary || "Your request has been sent for staff review.");
      setScreen("success");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not send the request.");
    } finally { setBusy(false); }
  };

  const toggleMic = () => {
    const SR = (typeof window !== "undefined") && ((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);
    if (!SR) { setError("Voice input isn't supported in this browser. Typing works the same way."); return; }
    if (listening) { recog.current?.stop(); return; }
    const r = new SR(); recog.current = r;
    r.lang = "en-US"; r.continuous = true; r.interimResults = true;
    const prefix = words.trim();
    r.onresult = (ev: any) => {
      let t = ""; for (let i = 0; i < ev.results.length; i++) t += ev.results[i][0].transcript + " ";
      const next = [prefix, t.trim()].filter(Boolean).join(" ").slice(0, 4000);
      setWords(next); setInputMode("voice"); schedule(next);
    };
    r.onend = () => setListening(false);
    r.onerror = () => setListening(false);
    try { r.start(); setListening(true); } catch { setListening(false); }
  };

  const accountOptions = Object.values(seen);

  // ---------- render ----------
  return (
    <main className="mx-auto min-h-screen max-w-6xl px-6 pb-24 pt-28">
      <Steps screen={screen} />

      {error && <div className="mb-6 rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</div>}

      {screen === "start" && (
        <section className="grid items-center gap-12 py-10 lg:grid-cols-2">
          <div>
            <p className="font-mono text-sm uppercase text-muted-foreground">A little clarity. A good next step.</p>
            <h1 className="mt-4 text-5xl font-semibold tracking-tight md:text-6xl">Tell us what you need.</h1>
            <p className="mt-6 max-w-md text-lg text-muted-foreground">
              You don&apos;t need to know the financial terms. Say it in your own words and we&apos;ll help put a
              request together, grounded in your real accounts.
            </p>
          </div>
          <div className="rounded-2xl border border-border bg-card/60 p-8 backdrop-blur">
            <h2 className="text-2xl font-semibold tracking-tight">Let&apos;s get on the same page.</h2>
            <p className="mt-2 text-muted-foreground">Choose a fictional client to try the experience.</p>
            <label className="mt-6 block text-sm font-medium">Demo client</label>
            <select value={clientId} onChange={(e) => setClientId(e.target.value)}
              className="mt-2 h-11 w-full rounded-md border border-border bg-background px-3 text-foreground">
              {(clients.length ? clients : [{ client_id: "CLIENT-017", display_name: "Mara Ellis" }]).map((c) => (
                <option key={c.client_id} value={c.client_id}>{c.display_name}</option>
              ))}
            </select>
            <Button onClick={begin} disabled={busy} size="lg" className="mt-6 w-full">
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <>Start a request <ArrowRight className="h-4 w-4" /></>}
            </Button>
            <p className="mt-3 text-center text-xs text-muted-foreground">Simulated client access · Fictional records only</p>
          </div>
        </section>
      )}

      {(screen === "describe" || screen === "review" || screen === "success") && (
        <div className="mb-8 overflow-hidden rounded-2xl border border-border bg-gradient-to-b from-white/[0.03] to-transparent shadow-[0_24px_64px_rgba(0,0,0,0.5)]">
          <div className="flex items-center justify-between border-b border-border px-5 py-3">
            <span className="font-mono text-xs font-semibold uppercase">Live routing</span>
            <span className="flex items-center gap-2 text-xs text-muted-foreground">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue-500 shadow-[0_0_10px_#2563eb]" />
              Interpreting with Amazon Bedrock
            </span>
          </div>
          <div className="h-[280px]"><RoutingGraph {...graphState} /></div>
        </div>
      )}

      {screen === "describe" && (
        <section>
          <p className="font-mono text-sm uppercase text-muted-foreground">A little clarity for {clientName.split(" ")[0]}</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight">What can we help you with?</h1>
          <div className="mt-8 grid gap-6 lg:grid-cols-[1.1fr_1fr]">
            <div className="rounded-2xl border border-border bg-card/60 p-6">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium">In your own words</label>
                <Button variant="outline" size="sm" onClick={toggleMic}>
                  <Mic className="h-4 w-4" /> {listening ? "Stop" : "Speak instead"}
                </Button>
              </div>
              <textarea
                value={words}
                onChange={(e) => { setWords(e.target.value); setInputMode("text"); setSelectedAccountId(null); schedule(e.target.value); }}
                rows={5}
                placeholder="For example, “I need help with the retirement money from my old job.”"
                className="mt-3 w-full resize-y rounded-lg border border-border bg-background/60 p-4 text-lg text-foreground placeholder:text-muted-foreground focus:border-white/40 focus:outline-none"
              />
              <div className="mt-4 flex items-center gap-3">
                <Button onClick={() => runTurn(words, selectedAccountId, inputMode)} disabled={busy || !words.trim()}>
                  {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <>Find the right next step <ArrowRight className="h-4 w-4" /></>}
                </Button>
                <span className="text-sm text-muted-foreground">{busy ? "Thinking…" : "Suggestions appear after you pause."}</span>
              </div>
            </div>

            <aside className="rounded-2xl border border-border bg-card/40 p-6">
              {turn?.question ? (
                <>
                  <p className="font-mono text-xs uppercase text-muted-foreground">Let&apos;s make sure we understand</p>
                  <h2 className="mt-2 text-xl font-medium">{turn.question}</h2>
                  {turn.uncertainty && (
                    <details className="mt-3 text-sm text-muted-foreground">
                      <summary className="cursor-pointer">Why am I being asked?</summary>
                      <p className="mt-2">{turn.uncertainty}</p>
                    </details>
                  )}
                  {turn.definitions?.length > 0 && (
                    <div className="mt-4 space-y-2">
                      {turn.definitions.map((d) => (
                        <details key={d.term} className="rounded-lg border border-border bg-background/50 p-3 text-sm">
                          <summary className="cursor-pointer font-medium">What is a {d.term}?</summary>
                          <p className="mt-2 text-muted-foreground">{d.plain}</p>
                        </details>
                      ))}
                    </div>
                  )}
                  <div className="mt-4 space-y-2">
                    {turn.suggestions.map((s) => (
                      <button key={s.id} onClick={() => selectSuggestion(s)}
                        className={`flex w-full items-center justify-between rounded-lg border px-4 py-3 text-left transition ${selectedAccountId === s.account_id ? "border-blue-500 bg-blue-500/10" : "border-border bg-background/50 hover:border-white/30"}`}>
                        <span className="text-sm">{s.label}</span>
                        <ArrowRight className="h-4 w-4 opacity-60" />
                      </button>
                    ))}
                  </div>
                </>
              ) : (
                <>
                  <p className="font-mono text-xs uppercase text-muted-foreground">No perfect words needed</p>
                  <p className="mt-2 text-muted-foreground">A life change, a question, or an account you can&apos;t quite name. Start anywhere, and watch the routing update above as you type.</p>
                </>
              )}
            </aside>
          </div>
          <div className="mt-8 flex items-center justify-between border-t border-border pt-6">
            <Button variant="ghost" onClick={() => { setSelectedAccountId(null); }}>None of these</Button>
            <Button onClick={toReview} disabled={!words.trim()}>Review my request <ArrowRight className="h-4 w-4" /></Button>
          </div>
        </section>
      )}

      {screen === "review" && (
        <section>
          <p className="font-mono text-sm uppercase text-muted-foreground">You have the final say</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight">Does this sound right?</h1>
          <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_1.4fr]">
            <div className="rounded-2xl border border-border bg-card/40 p-6">
              <p className="font-mono text-xs uppercase text-muted-foreground">What you said</p>
              <blockquote className="mt-3 border-l-2 border-border pl-4 text-lg italic text-foreground/90">{words}</blockquote>
              <Button variant="ghost" size="sm" className="mt-4" onClick={() => setScreen("describe")}>Edit my words</Button>
            </div>
            <div className="rounded-2xl border border-border bg-card/60 p-6">
              <label className="text-sm font-medium">What we understood</label>
              <textarea value={summary} onChange={(e) => setSummary(e.target.value)} rows={3}
                className="mt-2 w-full resize-y rounded-lg border border-border bg-background/60 p-3 text-foreground focus:border-white/40 focus:outline-none" />
              <label className="mt-4 block text-sm font-medium">Account to discuss</label>
              <select value={selectedAccountId ?? ""} onChange={(e) => setSelectedAccountId(e.target.value || null)}
                className="mt-2 h-11 w-full rounded-md border border-border bg-background px-3 text-foreground">
                <option value="">I&apos;m not sure / no account needed</option>
                {accountOptions.map((s) => <option key={s.account_id} value={s.account_id}>{s.label}</option>)}
              </select>
              <label className="mt-4 block text-sm font-medium">Amount to discuss <span className="text-muted-foreground">(optional, USD)</span></label>
              <input value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal"
                placeholder="Enter only if you want to discuss an amount"
                className="mt-2 h-11 w-full rounded-md border border-border bg-background px-3 text-foreground placeholder:text-muted-foreground focus:border-white/40 focus:outline-none" />
              <div className="mt-6 flex items-center justify-between">
                <Button variant="ghost" onClick={() => setScreen("describe")}><ArrowLeft className="h-4 w-4" /> Back</Button>
                <Button onClick={confirm} disabled={busy}>
                  {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <>Confirm and send <ArrowRight className="h-4 w-4" /></>}
                </Button>
              </div>
            </div>
          </div>
        </section>
      )}

      {screen === "success" && (
        <section className="mx-auto max-w-xl rounded-2xl border border-border bg-card/60 p-10 text-center">
          <span className="mx-auto grid h-16 w-16 place-items-center rounded-full border border-blue-500/40 bg-blue-500/10 text-blue-500 shadow-[0_0_40px_rgba(37, 99, 235,0.35)]"><Check className="h-7 w-7" /></span>
          <p className="mt-6 font-mono text-xs uppercase text-muted-foreground">Ready for staff review</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">Your request is on its way.</h1>
          <p className="mt-3 text-muted-foreground">{clientSummary}</p>
          <div className="mt-6 rounded-xl border border-blue-500/25 bg-blue-500/5 py-4">
            <span className="block text-xs text-muted-foreground">Your case number</span>
            <strong className="text-2xl text-blue-500">{caseId}</strong>
          </div>
          <div className="mt-6 flex justify-center gap-3">
            <Button asChild variant="outline"><Link href="/dashboard">View in advisor dashboard</Link></Button>
            <Button onClick={() => { setScreen("start"); setWords(""); setTurn(null); setSelectedAccountId(null); setSeen({}); setCaseId(null); }}>Start another</Button>
          </div>
        </section>
      )}
    </main>
  );
}

function Steps({ screen }: { screen: Screen }) {
  const step = screen === "review" ? 2 : screen === "success" ? 3 : 1;
  const items = ["Describe", "Review", "Send"];
  return (
    <ol className="mb-10 flex justify-center gap-10 text-sm text-muted-foreground">
      {items.map((label, i) => (
        <li key={label} className={`flex items-center gap-2 ${step === i + 1 ? "font-semibold text-foreground" : ""}`}>
          <span className={`grid h-7 w-7 place-items-center rounded-full border ${step === i + 1 ? "border-foreground bg-foreground text-background" : "border-border"}`}>{i + 1}</span>
          {label}
        </li>
      ))}
    </ol>
  );
}
