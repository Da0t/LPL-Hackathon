import React from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Reveal } from "./reveal";

export default function FinalCta() {
  return (
    <section className="relative z-10 overflow-hidden bg-[#0f1b33] py-24 text-white lg:py-32">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{ background: "radial-gradient(55% 70% at 80% 20%, rgba(22,119,255,0.35), transparent 70%)" }}
      />
      <Reveal className="relative mx-auto max-w-6xl px-6">
        <p className="max-w-3xl font-serif text-3xl italic leading-[1.25] text-white/85 md:text-5xl">
          “Your words. The right advisor.”
        </p>
        <p className="mt-6 max-w-xl text-pretty text-lg text-white/70">
          Try the client side, then open the advisor dashboard to see the same request arrive, clarified and ready to
          assign.
        </p>
        <div className="mt-9 flex flex-col gap-3 sm:flex-row">
          <Button asChild size="lg" className="bg-white px-6 text-base text-[#0f1b33] hover:bg-white/90">
            <Link href="/intake">
              Start a request <ArrowRight className="size-4" />
            </Link>
          </Button>
          <Button asChild size="lg" variant="ghost" className="border border-white/25 px-6 text-base text-white hover:bg-white/10 hover:text-white">
            <Link href="/dashboard">Advisor dashboard</Link>
          </Button>
        </div>
      </Reveal>
    </section>
  );
}
