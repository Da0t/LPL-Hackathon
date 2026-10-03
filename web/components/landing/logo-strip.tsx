import React from "react";
import { InfiniteSlider } from "@/components/ui/infinite-slider";
import { ProgressiveBlur } from "@/components/ui/progressive-blur";
import { LPLLogo, AWSLogo, BedrockLogo, TranscribeLogo } from "@/components/brand-logos";

export default function LogoStrip() {
  return (
    <section className="relative z-10 bg-background py-10" aria-label="Built with">
      <div className="mx-auto max-w-6xl px-6">
        <div className="flex flex-col items-center gap-6 md:flex-row">
          <p className="shrink-0 text-sm text-muted-foreground md:w-40 md:border-r md:border-border md:pr-6 md:text-right">
            Built with
          </p>
          <div className="relative w-full py-2">
            <InfiniteSlider speedOnHover={18} speed={36} gap={88}>
              <LPLLogo height={30} className="opacity-90 transition-opacity hover:opacity-100" />
              <AWSLogo height={32} className="opacity-90 transition-opacity hover:opacity-100" />
              <BedrockLogo height={32} className="opacity-90 transition-opacity hover:opacity-100" />
              <TranscribeLogo height={32} className="opacity-90 transition-opacity hover:opacity-100" />
            </InfiniteSlider>
            <div className="pointer-events-none absolute inset-y-0 left-0 w-24 bg-gradient-to-r from-background" />
            <div className="pointer-events-none absolute inset-y-0 right-0 w-24 bg-gradient-to-l from-background" />
            <ProgressiveBlur className="pointer-events-none absolute left-0 top-0 h-full w-24" direction="left" blurIntensity={1} />
            <ProgressiveBlur className="pointer-events-none absolute right-0 top-0 h-full w-24" direction="right" blurIntensity={1} />
          </div>
        </div>
      </div>
    </section>
  );
}
