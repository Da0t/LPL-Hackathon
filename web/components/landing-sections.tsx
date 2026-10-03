import React from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { MessageSquare, Sparkles, CheckCircle2, UserCheck } from "lucide-react";

const steps = [
  { icon: MessageSquare, title: "Say it plainly", body: "Clients speak or type in everyday words , “the Roth thing from my old job.” No financial jargon required." },
  { icon: Sparkles, title: "Coherent understands", body: "Amazon Bedrock interprets it against the client's real accounts and asks one clear question when something doesn't match." },
  { icon: CheckCircle2, title: "Confirm the request", body: "The client reviews a plain-language summary and confirms. Nothing , no account, no amount , is ever assumed." },
  { icon: UserCheck, title: "Right advisor, full context", body: "A structured, source-backed request reaches the right specialist, so the first conversation is the productive one." },
];

const stats = [
  { n: "61.2M", l: "Americans are 65+ (18% of the population) , the clients who struggle most with financial terms." },
  { n: "<50%", l: "of a financial advisor's time goes to direct client work today (Kitces Research)." },
  { n: "~73%", l: "of U.S. household net worth is held by households aged 55+ (Federal Reserve)." },
  { n: "$2.6T", l: "in assets and 32,000+ advisors at LPL Financial alone." },
];

export default function LandingSections() {
  return (
    <>
      {/* How it works */}
      <section className="relative z-10 border-t border-border bg-background py-20 md:py-28">
        <div className="mx-auto max-w-6xl px-6">
          <p className="font-mono text-xs uppercase tracking-wider text-primary">How it works</p>
          <h2 className="mt-3 max-w-2xl text-3xl font-semibold tracking-tight md:text-4xl">
            One clear path from a client's words to the right advisor.
          </h2>
          <div className="mt-12 grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            {steps.map((s, i) => (
              <div key={i} className="relative rounded-2xl border border-border bg-card p-6">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                  <s.icon className="h-5 w-5" />
                </div>
                <div className="mt-4 font-mono text-xs text-muted-foreground">0{i + 1}</div>
                <h3 className="mt-1 text-lg font-semibold">{s.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{s.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Impact */}
      <section className="relative z-10 border-t border-border bg-muted/30 py-20 md:py-28">
        <div className="mx-auto max-w-6xl px-6">
          <p className="font-mono text-xs uppercase tracking-wider text-primary">Why it matters</p>
          <h2 className="mt-3 max-w-2xl text-3xl font-semibold tracking-tight md:text-4xl">
            Demand is rising fastest among the clients who find it hardest.
          </h2>
          <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {stats.map((s, i) => (
              <div key={i} className="rounded-2xl border border-border bg-card p-6">
                <div className="text-4xl font-semibold tracking-tight text-foreground">{s.n}</div>
                <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{s.l}</p>
              </div>
            ))}
          </div>
          <p className="mt-8 max-w-3xl text-sm text-muted-foreground">
            <span className="font-medium text-foreground">Illustrative:</span> reclaiming even ~15 minutes per ambiguous
            request across 32,000+ advisors is tens of millions of dollars a year in recovered advisor capacity , before
            counting fewer misroutes and better retention. (Model, not a measured result.)
          </p>
        </div>
      </section>

      {/* CTA */}
      <section className="relative z-10 border-t border-border bg-background py-20 md:py-28">
        <div className="mx-auto max-w-3xl px-6 text-center">
          <h2 className="text-3xl font-semibold tracking-tight md:text-5xl">Get on the same page.</h2>
          <p className="mx-auto mt-4 max-w-xl text-muted-foreground">
            Try the live demo , describe a request in plain words and watch Coherent route it, powered by Amazon Bedrock.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Button asChild size="lg" className="px-6 text-base">
              <Link href="/intake"><span>Start a request →</span></Link>
            </Button>
            <Button asChild size="lg" variant="ghost" className="border border-border px-6 text-base hover:bg-foreground/5">
              <Link href="/dashboard"><span>Advisor dashboard</span></Link>
            </Button>
          </div>
        </div>
      </section>
    </>
  );
}
