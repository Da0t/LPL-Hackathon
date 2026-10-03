"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  Mic,
  Square,
  Printer,
  Sparkles,
  Check,
  CircleAlert,
  Lock,
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
  const [words, setWords] = useState(""),
    [turn, setTurn] = useState<any>(null),
    [summary, setSummary] = useState(""),
    [selected, setSelected] = useState(""),
    [amount, setAmount] = useState(""),
    [busy, setBusy] = useState(false),
    [sending, setSending] = useState(false),
    [paused, setPaused] = useState(false),
    [error, setError] = useState(""),
    [sendError, setSendError] = useState(""),
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
      Speech ? "" : "Speaking isn’t available in this browser. Typing works the same.",
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
          : "Listening. Use fictional information only.",
      );
    };
    r.onerror = () => {
      setListening(false);
      setSpeechHint(
        "The microphone is blocked or unavailable. Your words are kept; keep typing.",
      );
    };
    r.onend = () => {
      setListening(false);
      setSpeechHint((h) => (h.startsWith("Listening") ? "" : h));
    };
    try {
      r.start();
      setListening(true);
    } catch {
      setSpeechHint("The microphone could not start. Keep typing instead.");
    }
  }
  const account =
    client.accounts.find((a) => a.account_id === selected) || null;
  const amountNumber = amount.trim() ? Number(amount.replace(/,/g, "")) : null;
  const amountInvalid =
    !!amount.trim() &&
    (!/^(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?$/.test(amount.trim()) ||
      !Number.isFinite(amountNumber) ||
      amountNumber! <= 0);
  const preview: RequestDocument = saved || {
    client_id: client.client_id,
    client_name: client.profile.legal_name,
    case_id: sent,
    created_at: new Date().toISOString(),
    original_words: words,
    request_description: summary,
    amount_requested:
      amountNumber !== null && !amountInvalid ? amountNumber : null,
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
      setSendError("");
    } catch {
      setSendError(
        "Your request was sent, but its cloud document could not be saved yet. Retry saving the document below; do not send another request.",
      );
    }
  }
  async function send() {
    if (working.current || submitted.current || !session.current) return;
    stopMic();
    clearTimeout(timer.current);
    if (amountInvalid) return;
    working.current = true;
    setSending(true);
    setBusy(true);
    setSendError("");
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
      setSendError(e.message);
      if (["NETWORK", "INTERNAL_ERROR", "BAD_RESPONSE"].includes(e.code)) {
        setUncertain(true);
        setSendError(
          "Receipt could not be verified. Ask your team to check the request queue before submitting again. Your draft is preserved.",
        );
      }
    } finally {
      working.current = false;
      setSending(false);
      setBusy(false);
    }
  }
  const locked = sending || !!sent || uncertain;
  const reading = busy && !sending;
  const read = !!turn && synced === words.trim();
  // The one thing standing between the client and the send button, in their terms.
  const blocker = !words.trim()
    ? "Describe what you need to get started."
    : reading
      ? "We’re reading your latest wording…"
      : !read
        ? paused
          ? "Suggestions are paused. Choose “Check my request” so we can read your latest wording."
          : "Your wording changed. We’ll read it again when you pause typing."
        : !summary.trim()
          ? "Add a request description in step 3."
          : amountInvalid
            ? "Fix the amount in step 3, or leave it blank."
            : "";
  const status = listening
    ? speechHint
    : reading
      ? "Reading your words…"
      : read
        ? "We’ve read this. Check step 2."
        : words.trim()
          ? paused
            ? "Suggestions are paused."
            : "We’ll read this when you pause typing."
          : speechHint;
  return (
    <>
      <div className="request-top">
        <Link href="/workspace/requests">
          <ArrowLeft size={16} />
          My requests
        </Link>
        <span>
          {sent
            ? "Sent for staff review"
            : "Private draft. Nothing is sent until you confirm."}
        </span>
      </div>
      <PageHeading
        eyebrow="NEW REQUEST"
        title={sent ? "Your request is with your team." : "What do you need?"}
        description={
          sent
            ? "Here is what you sent and what happens next."
            : "Say it in your own words. We’ll check we understood, then you review the document before anything is sent."
        }
      />
      <div className="request-workspace">
        {sent ? (
          <section className="request-flow request-sent" role="status">
            <span className="sent-mark">
              <Check size={26} />
            </span>
            <h2>Request sent</h2>
            <p>
              Your reference is <strong>{sent}</strong>. No money has moved and
              no appointment has been booked.
            </p>
            {sendError && (
              <div className="send-blocker error" role="alert">
                <CircleAlert size={18} />
                <span>{sendError}</span>
              </div>
            )}
            {!saved && (
              <button
                className="portal-secondary"
                onClick={() => archive(sent)}
              >
                Retry document save
              </button>
            )}
            <h3>What happens next</h3>
            <ol className="next-steps">
              <li>
                <strong>Your team reads the document.</strong> They see exactly
                what is shown here, in your words.
              </li>
              <li>
                <strong>An advisor may ask you a question.</strong> It appears
                under My requests, where you can answer.
              </li>
              <li>
                <strong>You talk it through together.</strong> Nothing changes
                on your accounts until you and your advisor agree.
              </li>
            </ol>
            <div className="sent-actions">
              <Link className="portal-primary" href="/workspace/requests">
                View my requests <ArrowRight size={17} />
              </Link>
              <button
                className="portal-secondary"
                onClick={() => window.print()}
              >
                <Printer size={17} />
                Print or save PDF
              </button>
              <button
                className="link-button"
                onClick={() => window.location.reload()}
              >
                Start another request
              </button>
            </div>
          </section>
        ) : (
          <div className="request-flow">
            <section className="request-step describe-column">
              <div className="column-title">
                <span className={read ? "done" : "current"}>
                  {read ? <Check size={15} /> : "1"}
                </span>
                <div>
                  <h2>Tell us what you need</h2>
                  <p>Start anywhere. There are no wrong words.</p>
                </div>
              </div>
              <label htmlFor="request-words" className="sr-only">
                Your request
              </label>
              <textarea
                id="request-words"
                className="request-words"
                maxLength={4000}
                value={words}
                disabled={locked}
                autoFocus
                onChange={(e) => {
                  stopMic();
                  update(e.target.value);
                }}
                placeholder="For example: I need to discuss using some of the retirement money from my old job to help with care expenses."
              />
              {restoredNote && (
                <p className="profile-note">
                  We kept your draft from earlier. Nothing was sent. Choose
                  “Check my request” to continue.
                </p>
              )}
              <div className="voice-actions">
                {hasMic && (
                  <button
                    className={
                      listening
                        ? "portal-secondary listening"
                        : "portal-secondary"
                    }
                    type="button"
                    onClick={microphone}
                    disabled={locked}
                  >
                    {listening ? <Square size={17} /> : <Mic size={17} />}
                    {listening ? "Stop listening" : "Speak instead"}
                  </button>
                )}
                <button
                  className="portal-primary"
                  disabled={busy || !words.trim() || locked || read}
                  onClick={() => {
                    stopMic();
                    clearTimeout(timer.current);
                    run();
                  }}
                >
                  {reading ? "Reading…" : "Check my request"}
                  <ArrowRight size={17} />
                </button>
              </div>
              <div className="step-status">
                <p role="status">{status}</p>
                <button
                  className="link-button"
                  aria-pressed={paused}
                  onClick={() => {
                    stopMic();
                    isPaused.current = !paused;
                    setPaused(!paused);
                    clearTimeout(timer.current);
                  }}
                >
                  {paused ? "Resume suggestions" : "Pause suggestions"}
                </button>
              </div>
              {words.length > 3600 && (
                <p className="field-help">
                  {4000 - words.length} characters left.
                </p>
              )}
              {error && (
                <p className="portal-error" role="alert">
                  {error}
                </p>
              )}
            </section>
            <section
              className={
                turn || reading
                  ? "request-step clarify-column"
                  : "request-step clarify-column waiting"
              }
              aria-busy={reading}
            >
              <div className="column-title">
                <span
                  className={
                    turn && summary.trim() ? "done" : turn ? "current" : ""
                  }
                >
                  {turn && summary.trim() ? <Check size={15} /> : "2"}
                </span>
                <div>
                  <h2>Check we understood</h2>
                  <p>
                    {!turn
                      ? "Opens once we’ve read your words."
                      : turn.suggestions?.length
                        ? "Pick the closest match, or tell us none fit."
                        : "Here is how we read your request."}
                  </p>
                </div>
                {!turn && !reading && <Lock size={16} className="step-lock" />}
              </div>
              {turn?.degraded && (
                <p className="profile-note" role="status">
                  {turn.message ||
                    "We can’t interpret your words automatically right now. Check the description in step 3 yourself, or send it for your team to clarify."}
                </p>
              )}
              {turn ? (
                <>
                  <div className="clarifying-question" aria-live="polite">
                    <Sparkles size={20} />
                    <h3>{turn.question || "Does this capture what you mean?"}</h3>
                  </div>
                  {turn.uncertainty && (
                    <details>
                      <summary>Why are we asking?</summary>
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
                        disabled={busy || locked}
                        className={selected === s.account_id ? "selected" : ""}
                        aria-pressed={selected === s.account_id}
                        key={s.id}
                        onClick={() => {
                          stopMic();
                          clearTimeout(timer.current);
                          run(s.id);
                        }}
                      >
                        {s.label}
                        {selected === s.account_id ? (
                          <Check size={18} />
                        ) : (
                          <ArrowRight size={18} />
                        )}
                      </button>
                    ))}
                  </div>
                  <div className="request-alternatives">
                    <button
                      disabled={busy || locked}
                      onClick={() => run("none_of_these")}
                    >
                      None of these
                    </button>
                    <button
                      disabled={busy || locked}
                      onClick={() => run("talk_to_person")}
                    >
                      I’d rather talk to a person
                    </button>
                  </div>
                </>
              ) : (
                reading && (
                  <div className="step-reading" role="status">
                    <i />
                    <i />
                    <i />
                    <span className="sr-only">Reading your words…</span>
                  </div>
                )
              )}
            </section>
            <section
              className={
                turn
                  ? "request-step review-column"
                  : "request-step review-column waiting"
              }
            >
              <div className="column-title">
                <span className={turn && !blocker ? "done" : turn ? "current" : ""}>
                  {turn && !blocker ? <Check size={15} /> : "3"}
                </span>
                <div>
                  <h2>Confirm the details</h2>
                  <p>
                    {turn
                      ? "Edit anything. This is what your team will read."
                      : "Opens once we’ve read your words."}
                  </p>
                </div>
                {!turn && <Lock size={16} className="step-lock" />}
              </div>
              {turn && (
                <div className="review-fields">
                  <label>
                    Request description
                    <textarea
                      rows={4}
                      value={summary}
                      disabled={locked}
                      placeholder="A short description of what you’d like to discuss."
                      onChange={(e) => {
                        summaryEdited.current = true;
                        setSummary(e.target.value);
                      }}
                    />
                  </label>
                  <div className="review-pair">
                    <label>
                      Account to discuss
                      <select
                        value={selected}
                        disabled={locked}
                        onChange={(e) => setSelected(e.target.value)}
                      >
                        <option value="">Leave for the team to clarify</option>
                        {client.accounts.map((a) => (
                          <option value={a.account_id} key={a.account_id}>
                            {a.familiar_label} ({a.masked_identifier})
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Amount to discuss, in dollars (optional)
                      <input
                        inputMode="decimal"
                        value={amount}
                        disabled={locked}
                        aria-invalid={amountInvalid}
                        aria-describedby="amount-help"
                        placeholder="For example 6,000"
                        onChange={(e) => setAmount(e.target.value)}
                      />
                    </label>
                  </div>
                  <p
                    id="amount-help"
                    className={amountInvalid ? "field-help invalid" : "field-help"}
                  >
                    {amountInvalid
                      ? "Enter a dollar amount such as 6000 or 6,000.00, or leave it blank."
                      : "We never fill in an amount for you. If you change the account, reread the description."}
                  </p>
                </div>
              )}
            </section>
          </div>
        )}
        <section className="request-column document-column">
          <div className="column-title">
            <div>
              <h2>{sent ? "The document you sent" : "What your team will receive"}</h2>
              <p>
                {sent
                  ? "A copy is saved under My requests."
                  : "It updates as you go. Read it before you send."}
              </p>
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
          {!sent && (
            <div className="document-submit">
              {sendError ? (
                <div className="send-blocker error" role="alert">
                  <CircleAlert size={18} />
                  <span>{sendError}</span>
                </div>
              ) : (
                <div
                  className={blocker ? "send-blocker" : "send-blocker ready"}
                  role="status"
                >
                  {blocker ? <CircleAlert size={18} /> : <Check size={18} />}
                  <span>
                    {blocker ||
                      "Ready to send. By sending, you confirm this document reflects your request."}
                  </span>
                </div>
              )}
              <button
                className="portal-primary wide"
                disabled={busy || uncertain || !!blocker}
                onClick={send}
              >
                {sending ? "Sending…" : "Confirm and send request"}
                {!sending && <ArrowRight size={17} />}
              </button>
            </div>
          )}
        </section>
      </div>
    </>
  );
}
