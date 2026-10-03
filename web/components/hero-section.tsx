import React from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TextEffect } from "@/components/motion-primitives/text-effect";
import { AnimatedGroup } from "@/components/motion-primitives/animated-group";
import DecryptedText from "@/components/DecryptedText";
import { transitionVariants } from "@/lib/utils";
import TranslationStage from "@/components/translation-stage";

export default function HeroSection() {
  return (
    <section className="relative mx-auto grid max-w-6xl items-center gap-14 px-6 pb-20 pt-32 lg:min-h-[92vh] lg:grid-cols-[1.12fr_1fr] lg:gap-12 lg:pb-24 lg:pt-28">
      <div className="min-w-0 text-center lg:text-left">
        <DecryptedText
          text="Plain-language intake and advisor routing, built on Amazon Bedrock"
          animateOn="view"
          revealDirection="start"
          sequential
          useOriginalCharsOnly={false}
          speed={45}
          className="text-sm text-muted-foreground"
        />
        <TextEffect
          preset="fade-in-blur"
          speedSegment={0.3}
          as="h1"
          className="mt-6 text-balance text-[2.75rem] font-semibold leading-[1] tracking-[-0.03em] md:text-6xl lg:text-[3.6rem]"
        >
          Your words.
        </TextEffect>
        <TextEffect
          preset="fade-in-blur"
          speedSegment={0.3}
          delay={0.15}
          as="h1"
          className="text-balance text-[2.75rem] font-semibold leading-[1] tracking-[-0.03em] md:text-6xl lg:text-[3.6rem]"
        >
          The right advisor.
        </TextEffect>
        <TextEffect
          per="line"
          preset="fade-in-blur"
          speedSegment={0.3}
          delay={0.4}
          as="p"
          className="mx-auto mt-7 max-w-[46ch] text-pretty text-base leading-relaxed text-muted-foreground lg:mx-0 lg:text-lg"
        >
          Clients describe what they need the way they would say it to a friend. Coherent checks it against their real accounts, confirms the wording with them, and sends a request the right advisor can trust.
        </TextEffect>
        <AnimatedGroup
          variants={{ container: { visible: { transition: { staggerChildren: 0.05, delayChildren: 0.6 } } }, ...transitionVariants }}
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
        variants={{ container: { visible: { transition: { delayChildren: 0.25 } } }, ...transitionVariants }}
        className="mx-auto w-full min-w-0 max-w-[540px] lg:mx-0 lg:justify-self-end"
      >
        <TranslationStage variant="hero" />
      </AnimatedGroup>
    </section>
  );
}
