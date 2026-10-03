"use client";
import React, { useRef } from "react";
import { motion, useScroll, useTransform, useReducedMotion } from "motion/react";
import { Reveal } from "./reveal";

function Fact({ label, value, source }: { label: string; value: string; source: string }) {
  return (
    <div className="grid grid-cols-[7.5rem_1fr] gap-3 border-t border-border py-3 text-[14px] first:border-t-0 first:pt-0">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-foreground">
        {value}
        <span className="ml-2 inline-block rounded border border-border bg-[#f5f8ff] px-1.5 py-[1px] align-middle font-mono text-[10.5px] text-muted-foreground">
          {source}
        </span>
      </span>
    </div>
  );
}

export default function CaseRecord() {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 95%", "start 35%"] });
  const rotateX = useTransform(scrollYProgress, [0, 1], [10, 0]);
  const y = useTransform(scrollYProgress, [0, 1], [48, 0]);
  const opacity = useTransform(scrollYProgress, [0, 1], [0.5, 1]);

  return (
    <section className="relative z-10 bg-[#f5f8ff] py-24 lg:py-32">
      <div className="mx-auto max-w-6xl px-6">
        <Reveal className="max-w-2xl">
          <h2 className="text-balance text-3xl font-semibold tracking-tight md:text-5xl">What the advisor receives.</h2>
          <p className="mt-4 text-pretty text-lg text-muted-foreground">
            Not a polished paragraph. A record that keeps the client’s words, the confirmed wording, and the facts
            behind it, each with its source.
          </p>
        </Reveal>

        <div ref={ref} style={{ perspective: 1600 }} className="mt-14">
          <motion.article
            style={reduce ? undefined : { rotateX, y, opacity, transformOrigin: "50% 0%" }}
            className="landing-paper grid gap-10 rounded-[22px] p-7 md:p-10 lg:grid-cols-[1.05fr_1fr] lg:gap-14"
            aria-label="Example case record"
          >
            <div>
              <div className="flex items-center justify-between text-[12px] text-muted-foreground">
                <span>Case CASE-1043</span>
                <span>Submitted · staff review</span>
              </div>
              <p className="mt-6 text-[12px] text-muted-foreground">What the client said</p>
              <p className="mt-1.5 font-serif text-[24px] italic leading-[1.3] text-foreground md:text-[27px]">
                “I need six thousand dollars from the Roth thing from my old job.”
              </p>
              <p className="mt-7 text-[12px] text-muted-foreground">What the client confirmed</p>
              <p className="mt-1.5 text-[17px] leading-relaxed text-foreground">
                I want to speak with an advisor about using $6,000 from my retirement account from my former employer.
              </p>
              <p className="mt-7 text-[12px] text-muted-foreground">For staff</p>
              <p className="mt-1.5 text-[15px] leading-relaxed text-foreground">
                Client requests discussion of a possible $6,000 distribution from a rollover IRA. Describes the
                question, not advice to transact.
              </p>
              <div className="mt-6 flex flex-wrap gap-2 text-[12px]">
                <span className="rounded-full border border-border bg-white px-2.5 py-1">withdrawal or distribution</span>
                <span className="rounded-full border border-border bg-white px-2.5 py-1">retirement income</span>
                <span className="rounded-full border border-amber-300 bg-amber-50 px-2.5 py-1 text-amber-900">
                  wording did not match account type
                </span>
              </div>
            </div>

            <div className="lg:border-l lg:border-border lg:pl-14">
              <p className="text-[12px] text-muted-foreground">Account facts, each with its source</p>
              <div className="mt-4">
                <Fact label="Account" value="Rollover IRA ····4821" source="ACCOUNT-RECORD-201" />
                <Fact label="Balance" value="$84,000 as of Oct 1, 2026" source="ACCOUNT-RECORD-201" />
                <Fact label="Prior event" value="Rollover from a former workplace plan, Jun 12, 2023" source="EVENT-09" />
                <Fact label="Conflict" value="Client said “Roth”; no Roth IRA in the authorized list" source="ACCOUNT-RECORD-201" />
              </div>
              <p className="mt-8 text-[12px] text-muted-foreground">Routing</p>
              <div className="mt-3 flex items-center gap-3">
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-primary text-[12px] font-semibold text-white">JL</span>
                <span className="min-w-0 flex-1 text-[14px]">
                  <span className="block font-medium text-foreground">Jordan Lee, retirement advisor review</span>
                  <span className="block text-muted-foreground">Specialty match, available, offers phone meetings</span>
                </span>
              </div>
              <p className="mt-5 text-[12.5px] leading-relaxed text-muted-foreground">
                The balance is a snapshot, not an amount available to withdraw. Tax effects have not been assessed.
                A staff member assigns the case and records the reason.
              </p>
            </div>
          </motion.article>
        </div>
      </div>
    </section>
  );
}
