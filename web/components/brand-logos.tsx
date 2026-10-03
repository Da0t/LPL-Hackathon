// Simple, dependency-free wordmarks for the "Built on" strip.
// Styled text (not official logo art) so we avoid embedding third-party logo files.
import React from "react";

const base = "font-mono tracking-tight text-foreground whitespace-nowrap select-none";

export function LPLLogo({ className = "" }: { className?: string }) {
  return (
    <span className={`${base} ${className} font-semibold text-xl`}>
      LPL <span className="text-muted-foreground font-normal">Financial</span>
    </span>
  );
}

export function AWSLogo({ className = "" }: { className?: string }) {
  return (
    <span className={`${base} ${className} lowercase font-bold text-2xl`} aria-label="AWS">
      aws
    </span>
  );
}

export function BedrockLogo({ className = "" }: { className?: string }) {
  return (
    <span className={`${base} ${className} text-lg`}>
      Amazon <span className="font-semibold">Bedrock</span>
    </span>
  );
}

export function TranscribeLogo({ className = "" }: { className?: string }) {
  return (
    <span className={`${base} ${className} text-lg`}>
      Amazon <span className="font-semibold">Transcribe</span>
    </span>
  );
}

export function ClaudeLogo({ className = "" }: { className?: string }) {
  return (
    <span className={`${base} ${className} text-lg`}>
      Claude <span className="text-muted-foreground font-normal">Haiku 4.5</span>
    </span>
  );
}
