import HeroSection from "@/components/hero-section";
import FooterSection from "@/components/footer";
import Dither from "@/components/Dither";

export default function Home() {
    return (
        <>
            {/* Animated dither kept, toned down + blue-tinted so the content stays readable. */}
            <div className="pointer-events-none fixed inset-0 -z-10 opacity-[0.28]">
                <Dither
                    waveColor={[0.58, 0.70, 1.0]}
                    disableAnimation={false}
                    enableMouseInteraction
                    mouseRadius={0.3}
                    colorNum={4}
                    pixelSize={2}
                    waveAmplitude={0.22}
                    waveFrequency={3}
                    waveSpeed={0.04}
                />
            </div>
            <div className="pointer-events-none fixed inset-0 -z-10 bg-[radial-gradient(70%_55%_at_78%_-8%,rgba(37,99,235,0.08),transparent_62%)]" />
            <HeroSection />
            <FooterSection />
        </>
    )
}
