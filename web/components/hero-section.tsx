import React from 'react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { InfiniteSlider } from '@/components/ui/infinite-slider'
import { ProgressiveBlur } from '@/components/ui/progressive-blur'
import { TextEffect } from "@/components/motion-primitives/text-effect";
import { AnimatedGroup } from "@/components/motion-primitives/animated-group";
import DecryptedText from "@/components/DecryptedText";
import { transitionVariants } from "@/lib/utils";
import PipelinePreview from "@/components/pipeline-preview";
import { LPLLogo, AWSLogo, BedrockLogo, TranscribeLogo } from "@/components/brand-logos";

export default function HeroSection() {
    return (
        <main className="overflow-x-hidden">
            <section className="relative mx-auto grid max-w-6xl items-center gap-12 px-6 pb-16 pt-36 lg:min-h-screen lg:grid-cols-2 lg:gap-8 lg:pb-24 lg:pt-28">
                <div className="text-center lg:text-left">
                    <DecryptedText
                        text="AI intake & advisor routing · built on AWS"
                        animateOn="view" revealDirection="start" sequential useOriginalCharsOnly={false} speed={60}
                        className='font-mono text-muted-foreground bg-foreground/5 rounded-md uppercase text-xs md:text-sm px-1' />
                    <TextEffect preset="fade-in-blur" speedSegment={0.3} as="h1"
                        className="mt-6 text-balance text-5xl font-semibold leading-[0.95] md:text-7xl">
                        Your words.
                    </TextEffect>
                    <TextEffect preset="fade-in-blur" speedSegment={0.3} as="h1"
                        className="text-balance text-5xl font-semibold leading-[0.95] md:text-7xl">
                        The right advisor.
                    </TextEffect>
                    <TextEffect per="line" preset="fade-in-blur" speedSegment={0.3} delay={0.4} as="p"
                        className="mx-auto mt-6 max-w-md text-pretty text-base text-muted-foreground lg:mx-0 lg:text-lg">
                        Clients describe what they need in plain language. Coherent understands it,
                        confirms the details against their real accounts, and routes a clear request
                        to the right advisor , powered by Amazon Bedrock.
                    </TextEffect>
                    <AnimatedGroup
                        variants={{ container: { visible: { transition: { staggerChildren: 0.05, delayChildren: 0.6 } } }, ...transitionVariants }}
                        className="mt-9 flex flex-col items-center justify-center gap-2 sm:flex-row lg:justify-start">
                        <Button asChild size="lg" className="px-6 text-base">
                            <Link href="/intake"><span className="text-nowrap">Start a request →</span></Link>
                        </Button>
                        <Button asChild size="lg" variant="ghost" className="px-6 text-base border border-border hover:bg-foreground/5">
                            <Link href="/dashboard"><span className="text-nowrap">Advisor dashboard</span></Link>
                        </Button>
                    </AnimatedGroup>
                </div>
                <AnimatedGroup
                    variants={{ container: { visible: { transition: { delayChildren: 0.3 } } }, ...transitionVariants }}
                    className="w-full">
                    <PipelinePreview />
                </AnimatedGroup>
            </section>

            <section className="relative z-10 bg-background py-10">
                <div className="group relative m-auto max-w-5xl px-6">
                    <div className="flex flex-col items-center gap-6 md:flex-row">
                        <div className="md:max-w-44 md:border-r md:border-border md:pr-6">
                            <p className="text-center text-sm font-mono uppercase text-muted-foreground md:text-end">Built on</p>
                        </div>
                        <div className="relative w-full py-2 md:w-[calc(100%-11rem)]">
                            <InfiniteSlider speedOnHover={20} speed={40} gap={96}>
                                <div className="flex items-center"><LPLLogo /></div>
                                <div className="flex items-center"><AWSLogo /></div>
                                <div className="flex items-center"><BedrockLogo /></div>
                                <div className="flex items-center"><TranscribeLogo /></div>
                            </InfiniteSlider>
                            <div className="bg-gradient-to-r from-background absolute inset-y-0 left-0 w-20"></div>
                            <div className="bg-gradient-to-l from-background absolute inset-y-0 right-0 w-20"></div>
                            <ProgressiveBlur className="pointer-events-none absolute left-0 top-0 h-full w-20" direction="left" blurIntensity={1} />
                            <ProgressiveBlur className="pointer-events-none absolute right-0 top-0 h-full w-20" direction="right" blurIntensity={1} />
                        </div>
                    </div>
                </div>
            </section>
        </main>
    )
}
