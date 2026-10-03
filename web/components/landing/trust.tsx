import React from "react";
import { Reveal } from "./reveal";

const POINTS = [
  {
    title: "It never invents a fact.",
    body: "The model proposes; the records decide. An account, a balance, or an amount reaches a case only from a record the client is authorized to see.",
  },
  {
    title: "Every fact shows its source.",
    body: "Each account fact carries a record id and an as-of date. Conflicts between what the client said and what the records hold are written down, not smoothed over.",
  },
  {
    title: "A person decides.",
    body: "Possible fraud or unauthorized access goes to a specialist queue, never straight to a planning advisor. Staff choose the advisor and record why.",
  },
];

export default function Trust() {
  return (
    <section className="relative z-10 bg-background py-24 lg:py-32">
      <div className="mx-auto max-w-6xl px-6">
        <Reveal className="max-w-2xl">
          <h2 className="text-balance text-3xl font-semibold tracking-tight md:text-5xl">Built to be trusted with money questions.</h2>
        </Reveal>
        <Reveal className="mt-14 grid gap-10 md:grid-cols-3 md:gap-8" delay={0.1}>
          {POINTS.map((p) => (
            <div key={p.title} className="border-t-2 border-foreground pt-5">
              <h3 className="text-xl font-semibold tracking-tight">{p.title}</h3>
              <p className="mt-3 text-pretty text-[15px] leading-relaxed text-muted-foreground">{p.body}</p>
            </div>
          ))}
        </Reveal>
      </div>
    </section>
  );
}
