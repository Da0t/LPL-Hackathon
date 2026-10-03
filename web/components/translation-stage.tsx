"use client";
// The product in one surface: a client's plain words become a confirmed, routed
// request. Plays once on load, then waits; Replay is the only way it moves again.
// Everything shown comes from the synthetic demo record.

import React, { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence, useMotionValue, useSpring, useTransform, useReducedMotion } from "motion/react";
import { Check, RotateCcw } from "lucide-react";

const SENTENCE = "I need six thousand dollars from the Roth thing from my old job.";
const PHRASE = "the Roth thing from my old job";
const P_START = SENTENCE.indexOf(PHRASE);
const P_END = P_START + PHRASE.length;

type Step = 0 | 1 | 2 | 3 | 4 | 5;
// 0 ready · 1 listening · 2 account matched · 3 client confirmed · 4 request set · 5 routed

const STATUS: Record<Step, string> = {
  0: "Ready",
  1: "Listening",
  2: "Checking accounts",
  3: "Confirmed by the client",
  4: "Confirmed by the client",
  5: "Routed",
};

const ease = [0.2, 0.7, 0.2, 1] as const;

/** One line of the record: a label, then either a placeholder bar or the value. */
function Row({
  label,
  filled,
  minHeight,
  barWidth,
  children,
}: {
  label: string;
  filled: boolean;
  minHeight: number;
  barWidth: number;
  children: React.ReactNode;
}) {
  return (
    <div className="grid grid-cols-[76px_1fr] gap-x-4 py-3">
      <span className="text-[13px] leading-[22px] text-muted-foreground">{label}</span>
      <div className="relative min-w-0" style={{ minHeight }}>
        <AnimatePresence initial={false}>
          {filled ? (
            <motion.div
              key="value"
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, ease }}
            >
              {children}
            </motion.div>
          ) : (
            <motion.span
              key="bar"
              aria-hidden
              className="absolute left-0 top-[7px] h-2 rounded-full bg-[#edf1f6]"
              style={{ width: barWidth }}
              exit={{ opacity: 0, transition: { duration: 0.2 } }}
            />
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

export default function TranslationStage({ className = "" }: { className?: string }) {
  const reduce = useReducedMotion();
  const [step, setStep] = useState<Step>(0);
  const [typed, setTyped] = useState(0);
  const [done, setDone] = useState(false);
  const timers = useRef<number[]>([]);

  const clear = () => {
    timers.current.forEach((t) => window.clearTimeout(t));
    timers.current = [];
  };

  const play = useCallback(() => {
    clear();
    if (reduce) {
      setTyped(SENTENCE.length);
      setStep(5);
      setDone(true);
      return;
    }
    setDone(false);
    setStep(0);
    setTyped(0);
    const at = (ms: number, fn: () => void) => timers.current.push(window.setTimeout(fn, ms));
    // The card itself fades in over the first ~0.9s; typing starts once it is visible.
    const perChar = 28;
    const start = 1000;
    at(start, () => setStep(1));
    for (let i = 1; i <= SENTENCE.length; i++) at(start + i * perChar, () => setTyped(i));
    const typedDone = start + SENTENCE.length * perChar;
    at(typedDone + 450, () => setStep(2));
    at(typedDone + 2400, () => setStep(3));
    at(typedDone + 3100, () => setStep(4));
    at(typedDone + 3900, () => setStep(5));
    at(typedDone + 4600, () => setDone(true));
  }, [reduce]);

  useEffect(() => {
    play();
    return clear;
  }, [play]);

  // Subtle depth that follows the pointer. Springs keep it calm.
  const mx = useMotionValue(0);
  const my = useMotionValue(0);
  const rx = useSpring(useTransform(my, [-0.5, 0.5], [3, -3]), { stiffness: 120, damping: 18 });
  const ry = useSpring(useTransform(mx, [-0.5, 0.5], [-4, 4]), { stiffness: 120, damping: 18 });
  const onMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (reduce) return;
    const r = e.currentTarget.getBoundingClientRect();
    mx.set((e.clientX - r.left) / r.width - 0.5);
    my.set((e.clientY - r.top) / r.height - 0.5);
  };
  const onLeave = () => {
    mx.set(0);
    my.set(0);
  };

  const visible = SENTENCE.slice(0, typed);
  const before = visible.slice(0, P_START);
  const mid = visible.slice(P_START, P_END);
  const after = visible.slice(P_END);
  const confirmed = step >= 3;

  return (
    <div className={`relative min-w-0 ${className}`} style={{ perspective: 1400 }} onMouseMove={onMove} onMouseLeave={onLeave}>
      <div
        aria-hidden
        className={`pointer-events-none absolute -inset-8 -z-10 rounded-[40px] blur-2xl transition-opacity duration-700 ${
          step >= 2 ? "opacity-100" : "opacity-50"
        }`}
        style={{ background: "radial-gradient(60% 60% at 50% 40%, rgba(22,119,255,0.14), rgba(22,119,255,0) 70%)" }}
      />
      <motion.div
        style={reduce ? undefined : { rotateX: rx, rotateY: ry, transformStyle: "preserve-3d" }}
        className="landing-paper relative max-w-full rounded-2xl p-6"
      >
        {/* header */}
        <div className="flex items-center justify-between gap-3 text-[13px] leading-[22px] text-muted-foreground">
          <span>New request</span>
          <span className="inline-flex items-center gap-2">
            <span className="relative flex h-1.5 w-1.5">
              {step === 1 && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-60" />}
              <span className={`relative inline-flex h-1.5 w-1.5 rounded-full ${step >= 1 ? "bg-primary" : "bg-muted-foreground/40"}`} />
            </span>
            <AnimatePresence mode="wait" initial={false}>
              <motion.span
                key={STATUS[step]}
                initial={{ opacity: 0, y: 3 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -3 }}
                transition={{ duration: 0.22 }}
              >
                {STATUS[step]}
              </motion.span>
            </AnimatePresence>
          </span>
        </div>

        {/* the client's words */}
        <p className="mt-3 min-h-[81px] text-[17px] leading-[27px] text-foreground" aria-label={SENTENCE}>
          <span aria-hidden>
            {"“"}
            {before}
            <span
              className="rounded-[3px] whitespace-pre-wrap"
              style={{
                backgroundImage: "linear-gradient(#e2ecff, #e2ecff)",
                backgroundRepeat: "no-repeat",
                backgroundSize: step >= 2 ? "100% 100%" : "0% 100%",
                transition: "background-size 0.5s cubic-bezier(0.2, 0.7, 0.2, 1)",
                WebkitBoxDecorationBreak: "clone",
                boxDecorationBreak: "clone",
                padding: "0.08em 0.12em",
                margin: "0 -0.12em",
              }}
            >
              {mid}
            </span>
            {after}
            {typed >= SENTENCE.length && "”"}
            {step === 1 && typed < SENTENCE.length && (
              <span className="ml-0.5 inline-block h-[0.95em] w-[2px] translate-y-[0.15em] animate-pulse bg-primary align-baseline" />
            )}
          </span>
        </p>

        {/* the record */}
        <div className="mt-4 divide-y divide-border border-y border-border">
          <Row label="Account" filled={step >= 2} minHeight={76} barWidth={168}>
            <p className="text-[15px] font-medium leading-[22px] text-foreground">
              Rollover IRA <span className="font-normal text-muted-foreground">····4821</span>
            </p>
            <p className="text-[13px] leading-[22px] text-muted-foreground">Former employer plan. No Roth IRA on file.</p>
            <div className="mt-1.5 flex flex-wrap items-center gap-x-2.5 gap-y-1.5 text-[13px] leading-[22px] text-muted-foreground">
              <span>Is this the one?</span>
              <span
                className={`inline-flex h-[26px] items-center gap-1.5 rounded-full border px-2.5 font-medium transition-colors duration-300 ${
                  confirmed ? "border-primary bg-primary text-white" : "border-border bg-white text-foreground"
                }`}
              >
                {confirmed && <Check size={12} strokeWidth={3} />}
                Yes, that one
              </span>
            </div>
          </Row>
          <Row label="Request" filled={step >= 4} minHeight={22} barWidth={120}>
            <p className="text-[15px] font-medium leading-[22px] text-foreground">$6,000 withdrawal</p>
          </Row>
          <Row label="Advisor" filled={step >= 5} minHeight={44} barWidth={96}>
            <p className="text-[15px] font-medium leading-[22px] text-foreground">Jordan Lee</p>
            <p className="text-[13px] leading-[22px] text-muted-foreground">Retirement income specialist, available this week.</p>
          </Row>
        </div>

        {/* footer */}
        <div className="mt-4 flex items-center justify-between gap-3 text-[12px] leading-5 text-muted-foreground">
          <span>Synthetic records. A staff member makes the assignment.</span>
          <button
            type="button"
            onClick={play}
            className={`inline-flex shrink-0 items-center gap-1 rounded-md px-1.5 py-0.5 transition-opacity hover:text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary ${
              done ? "opacity-100" : "pointer-events-none opacity-0"
            }`}
            aria-label="Replay the example"
          >
            <RotateCcw size={12} /> Replay
          </button>
        </div>
      </motion.div>
    </div>
  );
}
