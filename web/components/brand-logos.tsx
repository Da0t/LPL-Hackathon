// Brand marks for the "Built with" strip. Drawn here as SVG so the page needs
// no third-party image files. The AWS service icons follow the AWS Architecture
// Icons conventions (category gradient square with a white glyph); the AWS smile
// and LPL wordmark are recognizable recreations, not official asset files.
import React from "react";

type MarkProps = { className?: string; height?: number; title?: string };

/** "aws" wordmark with the orange smile. */
export function AWSLogo({ className = "", height = 30, title = "Amazon Web Services" }: MarkProps) {
  const width = Math.round(height * 1.9);
  return (
    <svg className={className} width={width} height={height} viewBox="0 0 114 60" role="img" aria-label={title}>
      <title>{title}</title>
      <text
        x="2" y="40" fontFamily="var(--font-geist-sans), 'Helvetica Neue', Arial, sans-serif" fontWeight={800}
        fontSize="44" letterSpacing="-2.5" fill="#232F3E">aws</text>
      <path d="M9 48 C 36 60, 72 60, 101 46" stroke="#FF9900" strokeWidth="4.2" fill="none" strokeLinecap="round" />
      <path d="M93.5 41.5 L 102.5 45.5 L 95.5 52.5" stroke="#FF9900" strokeWidth="4.2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** LPL Financial wordmark. */
export function LPLLogo({ className = "", height = 30, title = "LPL Financial" }: MarkProps) {
  const width = Math.round(height * 5.1);
  return (
    <svg className={className} width={width} height={height} viewBox="0 0 306 60" role="img" aria-label={title}>
      <title>{title}</title>
      <text x="0" y="46" fontFamily="var(--font-geist-sans), 'Helvetica Neue', Arial, sans-serif" fontWeight={800} fontSize="52" letterSpacing="-3" fill="#0A2A5E">LPL</text>
      <rect x="104" y="14" width="2" height="34" rx="1" fill="#0A2A5E" opacity="0.35" />
      <text x="116" y="44" fontFamily="var(--font-geist-sans), 'Helvetica Neue', Arial, sans-serif" fontWeight={500} fontSize="33" letterSpacing="-0.5" fill="#0A2A5E">Financial</text>
    </svg>
  );
}

// ---------------------------------------------------------------------------
// AWS service icons: machine-learning category gradient + white glyph.
// ---------------------------------------------------------------------------

type ServiceKind = "bedrock" | "transcribe";

function Glyph({ kind }: { kind: ServiceKind }) {
  const s = { fill: "none", stroke: "#fff", strokeWidth: 3.2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  if (kind === "bedrock") {
    // Layers of strata with a node on top: foundation models.
    return (
      <g {...s}>
        <path d="M14 38 L32 47 L50 38" />
        <path d="M14 30 L32 39 L50 30" />
        <path d="M14 22 L32 31 L50 22 L32 13 Z" fill="rgba(255,255,255,0.18)" />
        <circle cx="32" cy="13" r="3.2" fill="#fff" stroke="none" />
      </g>
    );
  }
  // Speech waveform inside a bubble.
  return (
    <g {...s}>
      <path d="M14 15 h36 a3 3 0 0 1 3 3 v22 a3 3 0 0 1 -3 3 h-19 l-9 8 v-8 h-8 a3 3 0 0 1 -3 -3 v-22 a3 3 0 0 1 3 -3 Z" />
      <path d="M22 33 v-8 M28 36 v-14 M34 34 v-10 M40 37 v-16 M46 32 v-6" />
    </g>
  );
}

export function AwsServiceIcon({ kind, size = 40, className = "" }: { kind: ServiceKind; size?: number; className?: string }) {
  const id = `aws-${kind}-grad`;
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 64 64" aria-hidden="true">
      <defs>
        <linearGradient id={id} x1="0" y1="1" x2="1" y2="0">
          <stop offset="0" stopColor="#055F4E" />
          <stop offset="1" stopColor="#56C0A7" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="12" fill={`url(#${id})`} />
      <Glyph kind={kind} />
    </svg>
  );
}

function ServiceLogo({ kind, name, height, className }: { kind: ServiceKind; name: string; height: number; className: string }) {
  return (
    <span className={`inline-flex items-center gap-2.5 text-foreground ${className}`} role="img" aria-label={name}>
      <AwsServiceIcon kind={kind} size={height} />
      <span className="whitespace-nowrap text-[1.15rem] tracking-tight">
        Amazon <span className="font-semibold">{name.replace("Amazon ", "")}</span>
      </span>
    </span>
  );
}

export function BedrockLogo({ className = "", height = 30 }: MarkProps) {
  return <ServiceLogo kind="bedrock" name="Amazon Bedrock" height={height} className={className} />;
}

export function TranscribeLogo({ className = "", height = 30 }: MarkProps) {
  return <ServiceLogo kind="transcribe" name="Amazon Transcribe" height={height} className={className} />;
}
