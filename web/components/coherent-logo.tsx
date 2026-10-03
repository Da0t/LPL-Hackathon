import React from "react";

// Coherent mark , two overlapping rounded blue "blades" forming a C/leaf.
// Approximation of the brand mark. For the exact art, drop the file at
// /public/coherent-logo.png and it will be used automatically by <CoherentMark>.
export function CoherentMark({ className = "", size = 28 }: { className?: string; size?: number }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      style={{ isolation: "isolate" }}
      aria-hidden="true"
    >
      {/* light blade , lower-left */}
      <path
        d="M9 23 C9 16.5 13 14 19.5 15 C27.5 16.2 31 23 31 31 L31 36 C31 40.5 28 43 23.5 43 L15 43 C11 43 9 40 9 36 Z"
        fill="#AFCBFF"
      />
      {/* bright blade , upper; multiply darkens the overlap into a deeper blue */}
      <path
        d="M15 6 L30.5 6 C35 6 37 9.2 36 13.3 C34.6 20 29.8 24 23 24 C16 24 11.8 19 11.8 12 C11.8 8 13 6 15 6 Z"
        fill="#2E6BFF"
        style={{ mixBlendMode: "multiply" }}
      />
    </svg>
  );
}

export function CoherentLogo({ className = "", markSize = 26 }: { className?: string; markSize?: number }) {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <CoherentMark size={markSize} />
      <span className="text-lg font-semibold tracking-tight text-foreground">Coherent</span>
    </span>
  );
}

export default CoherentLogo;
