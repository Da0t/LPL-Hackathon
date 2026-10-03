import React from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TextEffect } from "@/components/motion-primitives/text-effect";
import { AnimatedGroup } from "@/components/motion-primitives/animated-group";
import { transitionVariants } from "@/lib/utils";
import TranslationStage from "@/components/translation-stage";
import CoherentLockup from "@/components/coherent-lockup";

export default function HeroSection() {
  return (
    <section className="relative mx-auto grid max-w-6xl items-center gap-14 px-6 pb-20 pt-32 lg:min-h-[88vh] lg:grid-cols-[1.05fr_1fr] lg:gap-14 lg:pb-24 lg:pt-28">
      <div className="min-w-0 text-center lg:text-left">
        <h1 className="m-0">
          <span className="sr-only">Coherent</span>
          <CoherentLockup className="mx-auto w-full max-w-[540px] lg:mx-0" />
        </h1>
        <TextEffect
          per="line"
          preset="fade-in-blur"
          delay={0.95}
          as="p"
          className="mt-6 text-balance text-xl tracking-[-0.015em] text-foreground/75 md:text-[1.45rem]"
        >
          Plain-language intake, routed to the right advisor.
        </TextEffect>
        <TextEffect
          per="line"
          preset="fade-in-blur"
          delay={1.1}
          as="p"
          className="mx-auto mt-7 max-w-[44ch] text-pretty text-base leading-relaxed text-muted-foreground lg:mx-0 lg:text-[1.0625rem]"
        >
          Clients say what they need the way they would say it to a friend. Coherent checks it against their real accounts, confirms the wording with them, and sends a request the right advisor can act on.
        </TextEffect>
        <AnimatedGroup
          variants={{ container: { visible: { transition: { staggerChildren: 0.05, delayChildren: 1.25 } } }, ...transitionVariants }}
          className="mt-9 flex flex-col items-center justify-center gap-2.5 sm:flex-row lg:justify-start"
        >
          <Button asChild size="lg" className="px-6 text-base">
            <Link href="/intake">
              Start a request <ArrowRight className="size-4" />
            </Link>
          </Button>
          <Button asChild size="lg" variant="ghost" className="border border-border px-6 text-base hover:bg-foreground/5">
            <Link href="/dashboard">Advisor dashboard</Link>
          </Button>
        </AnimatedGroup>
      </div>

      <AnimatedGroup
        variants={{ container: { visible: { transition: { delayChildren: 0.6 } } }, ...transitionVariants }}
        className="mx-auto w-full min-w-0 max-w-[500px] lg:mx-0 lg:justify-self-end"
      >
        <TranslationStage />
      </AnimatedGroup>
    </section>
  );
}
