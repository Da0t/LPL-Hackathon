"use client";
import React, { useRef, useState } from "react";
import { motion, useScroll, useTransform, useMotionValueEvent, useReducedMotion } from "motion/react";
import { Reveal } from "./reveal";

const STEPS = [
  {
    title: "Say it in your own words.",
    body: "Speak or type. No account numbers, no financial vocabulary. “The retirement money from my old job” is enough to start.",
    note: "Voice through Amazon Transcribe, or typed",
  },
  {
    title: "Confirm it against your real accounts.",
    body: "Coherent checks what you said against the accounts you actually hold. When something doesn’t match, it explains the term in plain language and asks one question. You confirm the wording before anything is sent.",
    note: "Nothing is assumed: not an account, not an amount",
  },
  {
    title: "Reach the right advisor.",
    body: "Your confirmed request arrives in a staff queue with every fact tied to a record. A person chooses the advisor and writes down why.",
    note: "Recommended by rules, decided by a person",
  },
];

export default function HowItWorks() {
  const ref = useRef<HTMLOListElement>(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 72%", "end 62%"] });
  const scaleY = useTransform(scrollYProgress, [0, 1], [0, 1]);
  const [reached, setReached] = useState(reduce ? 3 : 0);
  useMotionValueEvent(scrollYProgress, "change", (v) => {
    setReached(v > 0.92 ? 3 : v > 0.5 ? 2 : v > 0.06 ? 1 : 0);
  });

  return (
    <section className="relative z-10 bg-background py-24 lg:py-32">
      <div className="mx-auto max-w-6xl px-6">
        <Reveal className="max-w-2xl">
          <h2 className="text-balance text-3xl font-semibold tracking-tight md:text-5xl">Three steps. One request.</h2>
          <p className="mt-4 text-pretty text-lg text-muted-foreground">
            Intake today asks people to translate their lives into product names. Coherent does the translating,
            and lets the client check its work.
          </p>
        </Reveal>

        <ol ref={ref} className="relative mt-16 grid gap-14 lg:mt-20">
          {/* the line is drawn by scrolling: the sequence advances as you read */}
          <div aria-hidden className="absolute left-[19px] top-5 bottom-5 w-px bg-border lg:left-[23px]" />
          <motion.div
            aria-hidden
            style={{ scaleY: reduce ? 1 : scaleY, originY: 0 }}
            className="absolute left-[19px] top-5 bottom-5 w-px bg-primary lg:left-[23px]"
          />
          {STEPS.map((step, i) => {
            const active = reached > i;
            return (
              <li key={step.title} className="relative grid gap-5 pl-16 lg:grid-cols-[1fr_1.1fr] lg:gap-10 lg:pl-20">
                <span
                  className={`absolute left-0 top-0 grid h-10 w-10 place-items-center rounded-full border bg-background text-sm font-semibold transition-colors duration-500 lg:h-12 lg:w-12 lg:text-base ${
                    active ? "border-primary text-primary" : "border-border text-muted-foreground"
                  }`}
                >
                  {i + 1}
                </span>
                <h3 className="text-2xl font-semibold tracking-tight md:text-3xl">{step.title}</h3>
                <div>
                  <p className="text-pretty text-base leading-relaxed text-muted-foreground md:text-lg">{step.body}</p>
                  <p className="mt-3 inline-flex items-center gap-2 text-sm text-foreground">
                    <span className={`h-1.5 w-1.5 rounded-full transition-colors duration-500 ${active ? "bg-primary" : "bg-border"}`} />
                    {step.note}
                  </p>
                </div>
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}
