"use client";

import { useEffect, useState } from "react";
import { CoherentMark } from "@/components/coherent-logo";

// Shows the SVG mark + wordmark by default, and auto-upgrades to the real logo
// at /public/coherent-logo.png the moment that file exists (no broken image).
export function BrandLogo({ height = 30, className = "" }: { height?: number; className?: string }) {
  const [hasPng, setHasPng] = useState(false);

  useEffect(() => {
    const img = new window.Image();
    img.onload = () => setHasPng(true);
    img.onerror = () => setHasPng(false);
    img.src = "/coherent-logo.png";
  }, []);

  if (hasPng) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src="/coherent-logo.png" alt="Coherent" style={{ height }} className={`w-auto ${className}`} />;
  }

  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <CoherentMark size={Math.round(height * 0.95)} />
      <span className="text-lg font-semibold tracking-tight text-foreground">Coherent</span>
    </span>
  );
}

export default BrandLogo;
