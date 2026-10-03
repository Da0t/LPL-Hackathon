"use client";
// Value-over-time line in the Robinhood manner: no axes, a dotted line at the
// range's starting value, and a scrubbable cursor that reports the point under
// the pointer so the headline number can follow it.
import React, { useEffect, useMemo, useRef, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { shortDate, type Point } from "@/lib/portfolio";

const ease = [0.2, 0.7, 0.2, 1] as const;
const ts = (d: string) => Date.parse(d + "T00:00:00Z");

export function geometry(points: Point[], w: number, h: number, padTop: number, padBot: number) {
  if (!w || !points.length) return null;
  const t0 = ts(points[0].date);
  const span = Math.max(1, ts(points[points.length - 1].date) - t0);
  const vals = points.map((p) => p.value);
  let lo = Math.min(...vals);
  let hi = Math.max(...vals);
  if (hi - lo < 1) {
    lo -= 1;
    hi += 1;
  }
  const pad = (hi - lo) * 0.1;
  lo -= pad;
  hi += pad;
  const xs = points.map((p) => 1 + ((ts(p.date) - t0) / span) * (w - 2));
  const ys = points.map((p) => padTop + (1 - (p.value - lo) / (hi - lo)) * (h - padTop - padBot));
  return { xs, ys, d: xs.map((x, i) => `${i ? "L" : "M"}${x.toFixed(1)},${ys[i].toFixed(1)}`).join(" ") };
}

export default function PortfolioChart({
  points,
  accent,
  height = 260,
  onHover,
}: {
  points: Point[];
  accent: string;
  height?: number;
  onHover?: (p: Point | null) => void;
}) {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(0);
  const [hi, setHi] = useState<number | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    setW(el.clientWidth);
    const ro = new ResizeObserver((entries) => setW(entries[0].contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const geo = useMemo(() => geometry(points, w, height, 30, 12), [points, w, height]);

  const pick = (clientX: number) => {
    if (!geo || !ref.current) return;
    const x = clientX - ref.current.getBoundingClientRect().left;
    let best = 0;
    for (let i = 1; i < geo.xs.length; i++) if (Math.abs(geo.xs[i] - x) < Math.abs(geo.xs[best] - x)) best = i;
    if (best !== hi) {
      setHi(best);
      onHover?.(points[best]);
    }
  };
  const leave = () => {
    setHi(null);
    onHover?.(null);
  };

  const label = hi != null ? shortDate(points[hi].date, true) : "";
  const labelX = geo && hi != null ? Math.min(Math.max(geo.xs[hi], 48), w - 48) : 0;

  return (
    <div
      ref={ref}
      className="ov-chart"
      style={{ height }}
      onMouseMove={(e) => pick(e.clientX)}
      onMouseLeave={leave}
      onTouchStart={(e) => pick(e.touches[0].clientX)}
      onTouchMove={(e) => pick(e.touches[0].clientX)}
      onTouchEnd={leave}
    >
      {geo && (
        <svg width={w} height={height} role="img" aria-label="Recorded value over the selected period">
          <line x1={0} x2={w} y1={geo.ys[0]} y2={geo.ys[0]} stroke="#c3cad6" strokeDasharray="2 5" />
          <motion.path
            key={`${points[0]?.date}-${points.length}`}
            d={geo.d}
            fill="none"
            stroke={accent}
            strokeWidth={2}
            strokeLinejoin="round"
            strokeLinecap="round"
            initial={reduce ? false : { pathLength: 0, opacity: 0.6 }}
            animate={{ pathLength: 1, opacity: 1 }}
            transition={{ duration: 0.7, ease }}
          />
          {hi != null && (
            <g>
              <line x1={geo.xs[hi]} x2={geo.xs[hi]} y1={22} y2={height} stroke="#9aa3b2" strokeWidth={1} />
              <text x={labelX} y={14} textAnchor="middle" fontSize={12} fill="#657287">
                {label}
              </text>
              <circle cx={geo.xs[hi]} cy={geo.ys[hi]} r={5} fill={accent} stroke="#fff" strokeWidth={2} />
            </g>
          )}
        </svg>
      )}
    </div>
  );
}

/** Tiny line for list rows. */
export function Spark({ points, accent, width = 64, height = 22 }: { points: Point[]; accent: string; width?: number; height?: number }) {
  const geo = geometry(points, width, height, 2, 2);
  if (!geo) return null;
  return (
    <svg width={width} height={height} aria-hidden="true">
      <path d={geo.d} fill="none" stroke={accent} strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}
