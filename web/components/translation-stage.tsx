"use client";
// The product in one surface: a client's spoken words become a confirmed, routed
// request. Plays once on load as an orchestrated sequence, then waits; "Replay"
// is the only way it moves again. Everything shown is the synthetic demo record.

import React, { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence, useMotionValue, useSpring, useTransform, useReducedMotion } from "motion/react";
import { Check, RotateCcw } from "lucide-react";

const SENTENCE = "I need six thousand dollars from the Roth thing from my old job.";
const PHRASE = "the Roth thing from my old job";
const P_START = SENTENCE.indexOf(PHRASE);
const P_END = P_START + PHRASE.length;

type Step = 0 | 1 | 2 | 3 | 4 | 5;
// 0 empty · 1 listening (typing) · 2 understood · 3 client confirmed · 4 request confirmed · 5 routed

const STATUS: Record<Step, string> = {
  0: "Ready",
  1: "Listening",
  2: "Checking her accounts",
  3: "Confirmed by the client",
  4: "Request confirmed",
  5: "Routed to an advisor",
};

const ease = [0.2, 0.7, 0.2, 1] as const;

export default function TranslationStage({
  variant = "hero",
  className = "",
}: {
  variant?: "hero" | "login";
  className?: string;
}) {
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
    const perChar = 30;
    at(350, () => setStep(1));
    for (let i = 1; i <= SENTENCE.length; i++) at(350 + i * perChar, () => setTyped(i));
    const typedDone = 350 + SENTENCE.length * perChar;
    at(typedDone + 550, () => setStep(2));
    at(typedDone + 2500, () => setStep(3));
    at(typedDone + 3300, () => setStep(4));
    at(typedDone + 4500, () => setStep(5));
    at(typedDone + 5300, () => setDone(true));
  }, [reduce]);

  useEffect(() => {
    play();
    return clear;
  }, [play]);

  // Subtle depth that follows the pointer (hero only). Springs keep it calm.
  const mx = useMotionValue(0);
  const my = useMotionValue(0);
  const rx = useSpring(useTransform(my, [-0.5, 0.5], [4, -4]), { stiffness: 120, damping: 18 });
  const ry = useSpring(useTransform(mx, [-0.5, 0.5], [-5, 5]), { stiffness: 120, damping: 18 });
  const tilt = variant === "hero" && !reduce;
  const onMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!tilt) return;
    const r = e.currentTarget.getBoundingClientRect();
    mx.set((e.clientX - r.left) / r.width - 0.5);
    my.set((e.clientY - r.top) / r.height - 0.5);
  };
  const onLeave = () => {
    mx.set(0);
    my.set(0);
  };

  const hero = variant === "hero";
  const visible = SENTENCE.slice(0, typed);
  const before = visible.slice(0, P_START);
  const mid = visible.slice(P_START, P_END);
  const after = visible.slice(P_END);

  return (
    <div
      className={`relative min-w-0 ${className}`}
      style={{ perspective: 1400 }}
      onMouseMove={onMove}
      onMouseLeave={onLeave}
    >
      {/* soft glow behind the sheet */}
      <div
        aria-hidden
        className={`pointer-events-none absolute -inset-6 -z-10 rounded-[32px] blur-2xl transition-opacity duration-700 ${
          step >= 2 ? "opacity-100" : "opacity-40"
        }`}
        style={{ background: "radial-gradient(60% 60% at 50% 40%, rgba(22,119,255,0.16), rgba(22,119,255,0) 70%)" }}
      />
      <motion.div
        style={tilt ? { rotateX: rx, rotateY: ry, transformStyle: "preserve-3d" } : undefined}
        className={`landing-paper relative max-w-full rounded-[20px] ${hero ? "p-6 sm:p-7" : "p-4 sm:p-5"}`}
      >
        {/* status row */}
        <div className="flex items-center justify-between gap-3 text-[12px] text-muted-foreground">
          <span className="inline-flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              {step === 1 && (
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-60" />
              )}
              <span className={`relative inline-flex h-2 w-2 rounded-full ${step >= 1 ? "bg-primary" : "bg-muted-foreground/40"}`} />
            </span>
            <AnimatePresence mode="wait" initial={false}>
              <motion.span
                key={step}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.25 }}
              >
                {STATUS[step]}
              </motion.span>
            </AnimatePresence>
          </span>
          <span>Amazon Bedrock</span>
        </div>

        {/* the client's words */}
        <p
          className={`font-serif italic text-foreground ${hero ? "mt-5 text-[25px] leading-[1.3] sm:text-[28px]" : "mt-3 text-[20px] leading-[1.3]"}`}
          aria-label={SENTENCE}
        >
          <span aria-hidden>
            {"“"}
            {before}
            <span
              className="rounded-[3px] whitespace-pre-wrap"
              style={{
                backgroundImage: "linear-gradient(#dbe8ff, #dbe8ff)",
                backgroundRepeat: "no-repeat",
                backgroundSize: step >= 2 ? "100% 100%" : "0% 100%",
                transition: "background-size 0.55s cubic-bezier(0.2, 0.7, 0.2, 1)",
                WebkitBoxDecorationBreak: "clone",
                boxDecorationBreak: "clone",
                padding: "0.05em 0.1em",
                margin: "0 -0.1em",
              }}
            >
              {mid}
            </span>
            {after}
            {typed >= SENTENCE.length && "”"}
            {step === 1 && typed < SENTENCE.length && (
              <span className="ml-0.5 inline-block h-[0.9em] w-[2px] translate-y-[0.12em] animate-pulse bg-primary align-baseline" />
            )}
          </span>
        </p>

        {/* understanding: no Roth, closest match, one question, client answers */}
        <div className={hero ? "mt-5 min-h-[112px]" : "mt-3.5 min-h-[88px]"}>
          <AnimatePresence>
            {step >= 2 && (
              <motion.div
                key="understanding"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, ease }}
                className="relative pl-4 text-[14px] leading-relaxed"
              >
                <motion.span
                  aria-hidden
                  className="absolute left-0 top-1 bottom-1 w-[2px] rounded-full bg-primary"
                  initial={{ scaleY: 0 }}
                  animate={{ scaleY: 1 }}
                  style={{ originY: 0 }}
                  transition={{ duration: 0.5, ease }}
                />
                <p className="text-foreground">
                  No Roth IRA in these records.{" "}
                  <span className="text-muted-foreground">Closest match:</span>
                </p>
                <motion.span
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.25, duration: 0.45, ease }}
                  className="mt-1.5 inline-flex max-w-full flex-wrap items-center gap-x-2 gap-y-0.5 rounded-2xl border border-border bg-[#f5f8ff] px-3 py-1 text-[13px] text-foreground"
                >
                  <span className="font-medium">Rollover IRA</span>
                  <span className="text-muted-foreground">····4821</span>
                  <span className="text-muted-foreground">from a former employer</span>
                </motion.span>
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.6, duration: 0.4 }}
                  className="mt-2.5 flex flex-wrap items-center gap-2"
                >
                  <span className="text-muted-foreground">Is this the one?</span>
                  <motion.span
                    layout
                    className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-[3px] text-[12.5px] font-medium transition-colors duration-300 ${
                      step >= 3 ? "border-primary bg-primary text-white" : "border-border bg-white text-foreground"
                    }`}
                  >
                    {step >= 3 && <Check size={13} strokeWidth={3} />}
                    Yes, that one
                  </motion.span>
                  <motion.span
                    animate={{ opacity: step >= 3 ? 0.35 : 1 }}
                    className="inline-flex items-center rounded-full border border-border bg-white px-2.5 py-[3px] text-[12.5px] text-foreground"
                  >
                    Something else
                  </motion.span>
                </motion.div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* confirmed request */}
        <div className={`${hero ? "mt-5 pt-4" : "mt-3.5 pt-3"} border-t border-border`}>
          <AnimatePresence>
            {step >= 4 ? (
              <motion.div key="confirmed" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease }}>
                <p className="text-[12px] text-muted-foreground">Confirmed request</p>
                <p className={`mt-1 font-semibold tracking-tight text-foreground ${hero ? "text-[19px]" : "text-[17px]"}`}>
                  Discuss a $6,000 withdrawal
                </p>
                <p className="mt-0.5 text-[13px] text-muted-foreground">Rollover IRA ····4821, confirmed by the client in her own words</p>
              </motion.div>
            ) : (
              <motion.div key="pending" initial={{ opacity: 0.6 }} animate={{ opacity: 0.6 }} exit={{ opacity: 0 }} className="h-[58px]">
                <p className="text-[12px] text-muted-foreground">Confirmed request</p>
                <div className="mt-2 h-3 w-40 rounded bg-muted" />
                <div className="mt-2 h-2.5 w-56 rounded bg-muted" />
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* routed */}
        <div className={hero ? "mt-4 min-h-[52px]" : "mt-3 min-h-[48px]"}>
          <AnimatePresence>
            {step >= 5 && (
              <motion.div
                key="advisor"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, ease }}
                className={`flex items-center gap-3 rounded-2xl bg-[#f5f8ff] px-3.5 ${hero ? "py-3" : "py-2.5"}`}
              >
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-primary text-[12px] font-semibold text-white">JL</span>
                <span className="min-w-0 flex-1">
                  <span className="block text-[14px] font-medium text-foreground">Jordan Lee</span>
                  <span className="block truncate text-[12.5px] text-muted-foreground">Retirement income specialist, available</span>
                </span>
                <span className="shrink-0 rounded-full border border-primary/30 bg-white px-2.5 py-1 text-[11.5px] font-medium text-primary">Recommended</span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* footer */}
        <div className={`${hero ? "mt-4" : "mt-3"} flex items-center justify-between gap-3 text-[11.5px] text-muted-foreground`}>
          <span>Synthetic records. A staff member makes the assignment.</span>
          <button
            type="button"
            onClick={play}
            className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 transition-opacity hover:text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary ${
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
