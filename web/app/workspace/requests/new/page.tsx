"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {useAccessibility, ReadAloudButton} from "@/components/portal/accessibility";
import {
  ArrowLeft,
  ArrowRight,
  Mic,
  Square,
  Printer,
  FileCheck2,
  Sparkles,
  Check,
  Pause,
  Play,
} from "lucide-react";
import { useClient, PageHeading } from "@/components/portal/shell";
import { RequestPaper } from "@/components/portal/request-document";
import { RequestDocument, portalApi } from "@/lib/portal";
import {
  startIntake,
  intakeTurn,
  confirmIntake,
} from "@/lib/api";
export default function NewRequest() {
  const { client } = useClient();
  const accessibility = useAccessibility();
  const [humanHelp, setHumanHelp] = useState(false);
  useEffect(()=>{setHumanHelp(new URLSearchParams(window.location.search).get("help")==="person");},[]);
  const [words, setWords] = useState(""),
    [turn, setTurn] = useState<any>(null),
    [summary, setSummary] = useState(""),
    [selected, setSelected] = useState(""),
    [amount, setAmount] = useState(""),
    [busy, setBusy] = useState(false),
    [sending, setSending] = useState(false),
    [paused, setPaused] = useState(false),
    [error, setError] = useState(""),
    [synced, setSynced] = useState(""),
    [sent, setSent] = useState<string | null>(null),
    [saved, setSaved] = useState<RequestDocument | null>(null),
    [uncertain, setUncertain] = useState(false),
    [speechHint, setSpeechHint] = useState(""),
    [listening, setListening] = useState(false),
    [hasMic, setHasMic] = useState(false);
  const session = useRef<string | null>(null),
    working = useRef(false),
    version = useRef(0),
    latest = useRef(""),
    lastCall = useRef(0),
    timer = useRef<any>(null),
    recognition = useRef<any>(null),
    summaryEdited = useRef(false),
    inputMode = useRef<"text" | "voice">("text"),
    mounted = useRef(true),
    isPaused = useRef(false),
    submitted = useRef(false),
    restored = useRef(false),
    [restoredNote, setRestoredNote] = useState(false);
  const key = "coherent-draft-" + client.client_id;
  useEffect(() => {
    mounted.current = true;
    try {
      const draft = sessionStorage.getItem(key);
      if (draft) {
        setWords(draft);
        latest.current = draft;
        restored.current = true;
        setRestoredNote(true);
      }
    } catch {}
    const Speech =
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition;
    setHasMic(Boolean(Speech));
    setSpeechHint(
      Speech
        ? "Optional voice uses your browser’s speech service."
        : "Microphone unavailable here. Typing has all the same features.",
    );
    return () => {
      mounted.current = false;
      clearTimeout(timer.current);
      recognition.current?.abort();
    };
  }, [key]);
  function stopMic() {
    recognition.current?.stop();
    setListening(false);
  }
  function update(text: string, mode: "text" | "voice" = "text") {
    version.current++;
    latest.current = text;
    inputMode.current = mode;
    setWords(text);
    setSelected("");
    setTurn(null);
    setSynced("");
    setRestoredNote(false);
    summaryEdited.current = false;
    setSummary("");
    try {
      sessionStorage.setItem(key, text);
    } catch {}
    clearTimeout(timer.current);
    if (!isPaused.current) timer.current = setTimeout(() => run(), 1400);
  }
  async function run(option: string | null = null) {
    if (working.current || submitted.current || !latest.current.trim()) return;
    working.current = true;
    setBusy(true);
    setError("");
    const rev = version.current,
      text = latest.current.trim();
    try {
      if (!session.current)
        session.current = (await startIntake(client.client_id)).session_id;
      await new Promise((r) =>
        setTimeout(r, Math.max(0, 1300 - (Date.now() - lastCall.current))),
      );
      lastCall.current = Date.now();
      const result: any = await intakeTurn(session.current, client.client_id, {
        text,
        input_mode: inputMode.current,
        selected_option_id: option,
      });
      if (!mounted.current || rev !== version.current) return;
      setTurn(result);
      setSynced(text);
      if (option) {
        setSelected(result.selected_account_id || "");
      }
      if (!summaryEdited.current)
        setSummary(result.proposed_plain_language_request || text);
    } catch (e: any) {
      if (mounted.current) setError(e.message);
    } finally {
      working.current = false;
      if (mounted.current) {
        setBusy(false);
        if (rev !== version.current && !isPaused.current && !submitted.current)
          timer.current = setTimeout(() => run(), 1400);
      }
    }
  }
  function microphone() {
    accessibility.stop();
    if (listening) {
      stopMic();
      return;
    }
    const Speech =
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition;
    if (!Speech) return;
    const r = new Speech();
    recognition.current = r;
    r.continuous = true;
    r.interimResults = true;
    r.lang = "en-US";
    let prefix = latest.current;
    r.onresult = (e: any) => {
      let final = "",
        interim = "";
      for (let i = 0; i < e.results.length; i++) {
        if (e.results[i].isFinal) final += e.results[i][0].transcript + " ";
        else interim += e.results[i][0].transcript;
      }
      if (final)
        update([prefix, final.trim()].filter(Boolean).join(" "), "voice");
      setSpeechHint(
        interim
          ? "Listening: " + interim
          : "Listening with browser speech. Use fictional information.",
      );
    };
    r.onerror = () => {
      setListening(false);
      setSpeechHint(
        "Microphone unavailable or permission denied. Your words are preserved; keep typing.",
      );
    };
    r.onend = () => setListening(false);
    try {
      r.start();
      setListening(true);
    } catch {
      setSpeechHint("Microphone could not start. Continue by typing.");
    }
  }
  const questionText = turn ? [turn.question || "Does this capture what you mean?", ...(turn.suggestions || []).map((s:any,i:number)=>`Option ${i+1}: ${s.label}`)].filter(Boolean).join(". ") : "";
  useEffect(()=>{if(accessibility.prefs.autoRead && questionText && !listening) accessibility.speak(questionText); return ()=>accessibility.stop();},[questionText, accessibility.prefs.autoRead]);
  const account =
    client.accounts.find((a) => a.account_id === selected) || null;
  const amountNumber = amount.trim() ? Number(amount.replace(/,/g, "")) : null;
  const preview: RequestDocument = saved || {
    client_id: client.client_id,
    client_name: client.profile.legal_name,
    case_id: sent,
    created_at: new Date().toISOString(),
    original_words: words,
    request_description: summary,
    amount_requested:
      amountNumber !== null && Number.isFinite(amountNumber)
        ? amountNumber
        : null,
    account,
    history: client.activity.filter((e) => e.account_id === selected),
    status: sent ? "Submitted for review" : "Draft · not sent",
    synthetic_only: true,
  };
  async function archive(id: string) {
    try {
      const doc = await portalApi<RequestDocument>(
        "/portal/requests/" + id + "/archive",
        "POST",
      );
      setSaved(doc);
      setError("");
    } catch {
      setError(
        "Your request was sent, but its cloud document could not be saved yet. Retry saving the document below; do not send another request.",
      );
    }
  }
  async function send() {
    if (working.current || submitted.current || !session.current) return;
    stopMic();
    clearTimeout(timer.current);
    if (
      amount.trim() &&
      (!/^(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?$/.test(amount) ||
        !Number.isFinite(amountNumber) ||
        amountNumber! <= 0)
    ) {
      setError(
        "Enter a positive dollar amount such as 6000 or 6,000.00, or leave it blank.",
      );
      return;
    }
    working.current = true;
    setSending(true);
    setBusy(true);
    setError("");
    try {
      await new Promise((r) =>
        setTimeout(r, Math.max(0, 1300 - (Date.now() - lastCall.current))),
      );
      const result = await confirmIntake(session.current, client.client_id, {
        confirmed_plain_language_request: summary.trim(),
        selected_account_id: selected || null,
        amount_requested: amountNumber,
      });
      submitted.current = true;
      setSent(result.case_id);
      try {
        sessionStorage.removeItem(key);
      } catch {}
      await archive(result.case_id);
    } catch (e: any) {
      setError(e.message);
      if (["NETWORK", "INTERNAL_ERROR", "BAD_RESPONSE"].includes(e.code)) {
        setUncertain(true);
        setError(
          "Receipt could not be verified. Ask your team to check the request queue before submitting again. Your draft is preserved.",
        );
      }
    } finally {
      working.current = false;
      setSending(false);
      setBusy(false);
    }
  }
  return (
    <>
      <div className="request-top">
        <Link href="/workspace/requests">
          <ArrowLeft size={16} />
          My requests
        </Link>
        <span>
          {sent
            ? "Submitted for staff review"
            : "PRIVATE DRAFT · ONLY SENT WHEN YOU CONFIRM"}
        </span>
      </div>
      <PageHeading
        eyebrow="LET’S GET ON THE SAME PAGE"
        title={
          sent
            ? "Your request, ready for review."
            : "Your words. The complete picture."
        }
        description="Describe what you need, clarify the details, and review the document your team will receive."
      />
      {humanHelp && <div className="portal-success" role="status">A person can help. Describe what you need below, choose Talk to a person after clarification, then review and send. This does not place a call or submit anything automatically.</div>}
      {error && (
        <p className="portal-error" role="alert">
          {error}
        </p>
      )}
      {turn?.degraded && (
        <p className="profile-note" role="status">
          {turn.message || "Automatic interpretation is temporarily unavailable. Review your wording yourself or ask the team to clarify."}
        </p>
      )}
      {sent && (
        <div className="portal-success" role="status">
          <FileCheck2 size={20} />
          <span>
            Your request is saved. A member of your team can review it next. No money has moved. You can check progress and answer any questions in My requests.
          </span>
          {!saved && (
            <button onClick={() => archive(sent)} className="portal-secondary">
              Retry document save
            </button>
          )}
        </div>
      )}
      <div className="request-workspace">
        <section className="request-column describe-column">
          <div className="column-title">
            <span>01</span>
            <div>
              <h2>Tell us what you need</h2>
              <p>Start anywhere. Use your own words.</p>
            </div>
          </div>
          <label htmlFor="request-words">Your request</label>
          <textarea
            id="request-words"
            className="request-words"
            maxLength={4000}
            value={words}
            disabled={sending || !!sent || uncertain}
            onChange={(e) => {
              stopMic();
              update(e.target.value);
            }}
            placeholder="For example: I need to discuss using some of the retirement money from my old job to help with care expenses."
          />
          {restoredNote && (
            <p className="profile-note">
              Draft restored. Nothing was sent. Choose “Clarify my request” to
              continue.
            </p>
          )}
          <div className="voice-actions">
            <button
              className="portal-secondary"
              type="button"
              onClick={microphone}
              disabled={!hasMic || sending || !!sent || uncertain}
            >
              {listening ? <Square size={17} /> : <Mic size={17} />}{" "}
              {listening ? "Stop microphone" : "Speak instead"}
            </button>
            <button
              className="icon-button"
              aria-label={
                paused
                  ? "Resume automatic suggestions"
                  : "Pause automatic suggestions"
              }
              onClick={() => {
                stopMic();
                isPaused.current = !paused;
                setPaused(!paused);
                clearTimeout(timer.current);
              }}
            >
              {paused ? <Play size={18} /> : <Pause size={18} />}
            </button>
          </div>
          <p className="field-help" role="status">
            {speechHint}
          </p>
          <button
            className="portal-primary wide"
            disabled={busy || !words.trim() || !!sent || uncertain}
            onClick={() => {
              stopMic();
              clearTimeout(timer.current);
              run();
            }}
          >
            {busy ? "Working on your request…" : "Clarify my request"}
            <ArrowRight size={17} />
          </button>
          <div className="request-reassurance">
            <Sparkles size={19} />
            <p>
              We’ll match your words to your records, ask about anything
              unclear, and keep you in control.
            </p>
          </div>
          <p className="field-help">
            {paused
              ? "Automatic suggestions paused."
              : "Suggestions update after you pause typing."}{" "}
            Your draft stays in this browser tab until sent.
          </p>
        </section>
        <section className="request-column clarify-column">
          <div className="column-title">
            <span>02</span>
            <div>
              <h2>Make it clear</h2>
              <p>Check the meaning and the details.</p>
            </div>
          </div>
          {turn ? (
            <>
              <ReadAloudButton text={questionText} label="Read question and options" />
              <div className="clarifying-question" aria-live="polite">
                <Sparkles size={19} />
                <h3>{turn.question || "Does this capture what you mean?"}</h3>
              </div>
              {turn.uncertainty && (
                <details>
                  <summary>Why are we checking?</summary>
                  <p>{turn.uncertainty}</p>
                </details>
              )}
              {(turn.definitions || []).map((d: any) => (
                <details className="term-definition" key={d.term}>
                  <summary>What is {d.term}?</summary>
                  <p>{d.plain}</p>
                </details>
              ))}
              <div className="request-suggestions">
                {(turn.suggestions || []).slice(0, 3).map((s: any) => (
                  <button
                    disabled={busy || !!sent || uncertain}
                    className={selected === s.account_id ? "selected" : ""}
                    key={s.id}
                    onClick={() => {
                      stopMic();
                      clearTimeout(timer.current);
                      run(s.id);
                    }}
                  >
                    {s.label}
                    <ArrowUpRightIcon />
                  </button>
                ))}
              </div>
              <div className="request-alternatives">
                <button
                  disabled={busy || !!sent || uncertain}
                  onClick={() => run("none_of_these")}
                >
                  None of these
                </button>
                <button
                  disabled={busy || !!sent || uncertain}
                  onClick={() => run("talk_to_person")}
                >
                  Talk to a person
                </button>
              </div>
            </>
          ) : (
            <div className="clarification-empty">
              <Sparkles size={27} />
              <h3>Clarity starts with your words.</h3>
              <p>
                Write or speak your request. We’ll help connect it to the right
                account and context.
              </p>
            </div>
          )}
          <div className="review-fields">
            <label>
              Request description
              <textarea
                aria-label="Request description"
                rows={5}
                value={summary}
                disabled={sending || !!sent || uncertain}
                placeholder="The wording you’ll confirm appears here."
                onChange={(e) => {
                  summaryEdited.current = true;
                  setSummary(e.target.value);
                }}
              />
            </label>
            <label>
              Account to discuss
              <select
                aria-label="Account to discuss"
                value={selected}
                disabled={sending || !!sent || uncertain}
                onChange={(e) => setSelected(e.target.value)}
              >
                <option value="">Leave for the team to clarify</option>
                {client.accounts.map((a) => (
                  <option value={a.account_id} key={a.account_id}>
                    {a.familiar_label} · {a.masked_identifier}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Amount to discuss (USD, optional)
              <input
                inputMode="decimal"
                value={amount}
                disabled={sending || !!sent || uncertain}
                placeholder="Enter an amount yourself"
                onChange={(e) => setAmount(e.target.value)}
              />
            </label>
            <p className="field-help">
              Review the wording if you change accounts. Amounts are never
              filled in for you.
            </p>
          </div>
        </section>
        <section className="request-column document-column">
          <div className="column-title">
            <span>03</span>
            <div>
              <h2>Your request document</h2>
              <p>Read the exact information you’ll share.</p>
            </div>
            <button
              className="icon-button"
              aria-label="Print or save PDF"
              onClick={() => window.print()}
            >
              <Printer size={19} />
            </button>
          </div>
          <div className="paper-scroll">
            <RequestPaper document={preview} />
          </div>
          <div className="document-submit">
            <p>
              By sending, you confirm this description and the selected details
              reflect your request.
            </p>
            <button
              className="portal-primary wide"
              disabled={
                busy ||
                !!sent ||
                uncertain ||
                !summary.trim() ||
                synced !== words.trim()
              }
              onClick={send}
            >
              {sent ? (
                <>
                  <Check size={18} />
                  Request sent
                </>
              ) : busy ? (
                "Working…"
              ) : (
                <>
                  Confirm and send request
                  <ArrowRight size={17} />
                </>
              )}
            </button>
            {sent && (
              <Link href="/workspace/requests">View my saved requests →</Link>
            )}
          </div>
        </section>
      </div>
    </>
  );
}
function ArrowUpRightIcon() {
  return (
    <svg
      width="17"
      height="17"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
    >
      <path d="M6 18 18 6M6 6h12v12" />
    </svg>
  );
}
