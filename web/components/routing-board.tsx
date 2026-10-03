"use client";
// The other half of the product, for the sign-in page: requests arriving in
// plain words and being matched to the advisor whose specialty fits. Runs on a
// loop over synthetic requests and the demo advisor roster. The hero shows the
// client's side; this shows the practice's side.

import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import { motion, AnimatePresence, useReducedMotion } from "motion/react";

type Advisor = { id: string; initials: string; name: string; focus: string };
type Request = { words: string; tag: string; to: string };

const ADVISORS: Advisor[] = [
  { id: "jl", initials: "JL", name: "Jordan Lee", focus: "Retirement income" },
  { id: "tm", initials: "TM", name: "Taylor Morgan", focus: "Investment planning" },
  { id: "pr", initials: "PR", name: "Priya Raman", focus: "Beneficiaries and estate" },
  { id: "ca", initials: "CA", name: "Chris Avery", focus: "Account service" },
];

const REQUESTS: Request[] = [
  { words: "Can I take six thousand from the Roth thing from my old job?", tag: "Withdrawal", to: "jl" },
  { words: "Is now a bad time to put more into the market?", tag: "Investment question", to: "tm" },
  { words: "I need to change who gets my accounts if something happens to me.", tag: "Beneficiary change", to: "pr" },
  { words: "My address changed and I never got my tax form.", tag: "Account update", to: "ca" },
  { words: "Can I move my old 401(k) over here?", tag: "Rollover", to: "tm" },
  { words: "I retire in March. How do I turn this into a paycheck?", tag: "Retirement income", to: "jl" },
];

type Pt = { x: number; y: number };
type Geom = { start: Pt; pill: Pt; rows: Record<string, Pt> };
type Phase = "arrive" | "tagged" | "travel" | "landed";

const ease = [0.2, 0.7, 0.2, 1] as const;

function curve(a: Pt, b: Pt) {
  const dx = b.x - a.x;
  return `M${a.x},${a.y} C${a.x + dx * 0.5},${a.y} ${b.x - dx * 0.5},${b.y} ${b.x},${b.y}`;
}

// Points along the same curve, spaced so the traveller eases out as it arrives.
function samples(a: Pt, b: Pt, n = 30) {
  const dx = b.x - a.x;
  const p1 = { x: a.x + dx * 0.5, y: a.y };
  const p2 = { x: b.x - dx * 0.5, y: b.y };
  const xs: number[] = [];
  const ys: number[] = [];
  for (let i = 0; i <= n; i++) {
    const s = i / n;
    const t = s < 0.5 ? 2 * s * s : 1 - Math.pow(-2 * s + 2, 2) / 2; // ease in-out
    const u = 1 - t;
    xs.push(u * u * u * a.x + 3 * u * u * t * p1.x + 3 * u * t * t * p2.x + t * t * t * b.x);
    ys.push(u * u * u * a.y + 3 * u * u * t * p1.y + 3 * u * t * t * p2.y + t * t * t * b.y);
  }
  return { xs, ys };
}

function Tag({ children, ghost = false }: { children: React.ReactNode; ghost?: boolean }) {
  return (
    <span
      className={`inline-flex h-[26px] items-center whitespace-nowrap rounded-full border px-2.5 text-[12.5px] font-medium ${
        ghost ? "border-transparent bg-transparent text-transparent" : "border-primary/25 bg-white text-primary shadow-[0_1px_2px_rgba(21,32,51,0.06)]"
      }`}
    >
      {children}
    </span>
  );
}

export default function RoutingBoard({ className = "" }: { className?: string }) {
  const reduce = !!useReducedMotion();
  const boardRef = useRef<HTMLDivElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  const pillRef = useRef<HTMLSpanElement>(null);
  const rowRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const [geom, setGeom] = useState<Geom | null>(null);
  const [i, setI] = useState(0);
  const [phase, setPhase] = useState<Phase>("arrive");
  const [counts, setCounts] = useState<Record<string, number>>({ jl: 2, tm: 1, pr: 3, ca: 1 });
  const [flash, setFlash] = useState<string | null>(null);

  const req = REQUESTS[i % REQUESTS.length];

  // Positions in board coordinates: the card's right edge (connector start),
  // the tag's centre (traveller start), and each advisor row's left edge.
  useLayoutEffect(() => {
    const measure = () => {
      const board = boardRef.current, card = cardRef.current, pill = pillRef.current;
      if (!board || !card || !pill) return;
      const b = board.getBoundingClientRect();
      const c = card.getBoundingClientRect();
      const p = pill.getBoundingClientRect();
      const rows: Record<string, Pt> = {};
      for (const a of ADVISORS) {
        const r = rowRefs.current[a.id]?.getBoundingClientRect();
        if (r) rows[a.id] = { x: r.left - b.left, y: r.top - b.top + r.height / 2 };
      }
      setGeom({
        start: { x: c.right - b.left, y: c.top - b.top + c.height / 2 },
        pill: { x: p.left - b.left + p.width / 2, y: p.top - b.top + p.height / 2 },
        rows,
      });
    };
    measure();
    const ro = new ResizeObserver(measure);
    if (boardRef.current) ro.observe(boardRef.current);
    return () => ro.disconnect();
  }, []);

  // One request's life: arrive, get tagged, travel, land. Then the next one.
  useEffect(() => {
    const t: number[] = [];
    const at = (ms: number, fn: () => void) => t.push(window.setTimeout(fn, ms));
    setPhase("arrive");
    at(1000, () => setPhase("tagged"));
    if (!reduce) at(1700, () => setPhase("travel"));
    at(reduce ? 2200 : 2600, () => {
      setPhase("landed");
      setCounts((c) => ({ ...c, [req.to]: c[req.to] + 1 }));
      setFlash(req.to);
    });
    at(3400, () => setFlash(null));
    at(4300, () => setI((n) => n + 1));
    return () => t.forEach((id) => window.clearTimeout(id));
  }, [i, reduce, req.to]);

  const target = geom?.rows[req.to];
  const path = geom && target ? curve(geom.start, target) : "";
  const travel = geom && target ? samples(geom.pill, { x: target.x + 20, y: target.y }) : null;

  return (
    <div ref={boardRef} className={`relative ${className}`}>
      {/* connectors */}
      <svg className="pointer-events-none absolute inset-0 h-full w-full overflow-visible" aria-hidden="true">
        {geom &&
          ADVISORS.map((a) => geom.rows[a.id] && (
            <path key={a.id} d={curve(geom.start, geom.rows[a.id])} fill="none" stroke="#c9d8f0" strokeWidth="1.5" />
          ))}
        {path && phase !== "arrive" && (
          <motion.path
            key={i}
            d={path}
            fill="none"
            stroke="#1677ff"
            strokeWidth="2"
            strokeLinecap="round"
            initial={reduce ? false : { pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 0.6, ease }}
          />
        )}
      </svg>

      <div className="grid grid-cols-[minmax(0,1fr)_72px_minmax(0,1.15fr)] items-center">
        {/* incoming request */}
        <div
          ref={cardRef}
          className="relative z-10 flex min-h-[150px] flex-col justify-between rounded-2xl border border-[#e3e9f1] bg-white p-4 shadow-[0_1px_2px_rgba(21,32,51,0.04),0_18px_40px_-24px_rgba(21,32,51,0.25)]"
        >
          <div className="flex items-center gap-2 text-[12px] leading-5 text-muted-foreground">
            <span className="relative flex h-1.5 w-1.5">
              {phase === "arrive" && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-60" />}
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-primary" />
            </span>
            New request
          </div>
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={i}
              initial={reduce ? false : { opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4, transition: { duration: 0.18 } }}
              transition={{ duration: 0.4, ease }}
              className="mt-2 text-[14px] leading-[21px] text-foreground"
            >
              “{req.words}”
            </motion.div>
          </AnimatePresence>
          <div className="mt-3 h-[26px]">
            {/* the ghost keeps the slot measured even before a tag exists */}
            <span ref={pillRef} className="inline-flex">
              <AnimatePresence initial={false}>
                {phase === "tagged" || (reduce && phase === "landed") ? (
                  <motion.span
                    key={`tag-${i}`}
                    initial={reduce ? false : { opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, transition: { duration: 0.1 } }}
                    transition={{ duration: 0.3, ease }}
                  >
                    <Tag>{req.tag}</Tag>
                  </motion.span>
                ) : (
                  <span key="ghost">
                    <Tag ghost>{req.tag}</Tag>
                  </span>
                )}
              </AnimatePresence>
            </span>
          </div>
        </div>

        <div aria-hidden="true" />

        {/* advisors */}
        <div className="relative z-10 flex flex-col gap-2.5">
          {ADVISORS.map((a) => {
            const lit = flash === a.id;
            return (
              <div
                key={a.id}
                ref={(el) => {
                  rowRefs.current[a.id] = el;
                }}
                className={`flex items-center gap-3 rounded-xl border px-3 py-2 transition-colors duration-500 ${
                  lit ? "border-primary/40 bg-[#e8f0ff]" : "border-[#e3e9f1] bg-white"
                }`}
              >
                <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-[#e3edff] text-[11.5px] font-semibold text-primary">
                  {a.initials}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[13.5px] font-medium leading-[18px] text-foreground">{a.name}</span>
                  <span className="block truncate text-[12px] leading-4 text-muted-foreground">{a.focus}</span>
                </span>
                <AnimatePresence mode="popLayout" initial={false}>
                  <motion.span
                    key={counts[a.id]}
                    initial={reduce ? false : { scale: 0.6, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    exit={{ scale: 0.6, opacity: 0 }}
                    transition={{ type: "spring", stiffness: 400, damping: 22 }}
                    className={`grid h-[22px] min-w-[22px] shrink-0 place-items-center rounded-full px-1.5 text-[11.5px] font-medium tabular-nums ${
                      lit ? "bg-primary text-white" : "bg-[#eef2f7] text-foreground"
                    }`}
                  >
                    {counts[a.id]}
                  </motion.span>
                </AnimatePresence>
              </div>
            );
          })}
        </div>
      </div>

      {/* the tag in flight */}
      {travel && phase === "travel" && (
        <motion.div
          key={`fly-${i}`}
          className="pointer-events-none absolute left-0 top-0 z-20"
          initial={{ x: travel.xs[0], y: travel.ys[0] }}
          animate={{ x: travel.xs, y: travel.ys }}
          transition={{ duration: 0.9, ease: "linear" }}
        >
          <div className="-translate-x-1/2 -translate-y-1/2">
            <Tag>{req.tag}</Tag>
          </div>
        </motion.div>
      )}
    </div>
  );
}
