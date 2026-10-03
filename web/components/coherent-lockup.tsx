"use client";
// The Coherent logo as a living object for the hero. The mark is redrawn as two
// SVG pieces traced from /public/coherent-icon.png, so each can move on its own;
// the wordmark is the real art, cropped from /public/coherent-logo.png.
//
// Sizes are percentages of the lockup width, in the PNG's own units
// (icon 375×356 at x=36,y=25; wordmark from x=452 to the right edge; height 407).

import React, { useState } from "react";
import { motion, useReducedMotion } from "motion/react";

const LOGO_W = 1848;
const LOGO_H = 407;
const ICON = { x: 18, y: 19, w: 375, h: 356 }; // bounds inside coherent-icon.png
const ICON_LEFT = 36;
const ICON_TOP = 25;
const WORD_X = 452;
const WORD_W = LOGO_W - WORD_X;
const LOCKUP_W = LOGO_W - ICON_LEFT;

const pct = (n: number) => `${(n / LOCKUP_W) * 100}%`;

// Light piece: the lower "C". Bright piece: the upper arm and stem.
const LIGHT =
  "M132 128 H162 A90 90 0 0 1 252 218 V273 H343 A12 12 0 0 1 355 285 V297 A78 78 0 0 1 277 375 H132 A114 114 0 0 1 18 261 V242 A114 114 0 0 1 132 128 Z";
const BRIGHT =
  "M205 19 H375 A18 18 0 0 1 393 37 V88 A92 92 0 0 1 301 180 H252 V274 H205 A100 100 0 0 1 105 174 V119 A100 100 0 0 1 205 19 Z";

type Vec = { x: number; y: number };

function Piece({
  d,
  fill,
  from,
  drift,
  hover,
  delay,
  hovered,
  reduce,
  blend,
}: {
  d: string;
  fill: string;
  from: Vec;
  drift: Vec;
  hover: Vec;
  delay: number;
  hovered: boolean;
  reduce: boolean;
  blend?: boolean;
}) {
  return (
    // 1. arrival: the piece slides in and settles
    <motion.g
      initial={reduce ? false : { x: from.x, y: from.y, opacity: 0 }}
      animate={{ x: 0, y: 0, opacity: 1 }}
      transition={{ type: "spring", stiffness: 150, damping: 19, delay, opacity: { duration: 0.3, delay } }}
    >
      {/* 2. response: the pieces part slightly under the pointer and snap back */}
      <motion.g
        animate={hovered ? { x: hover.x, y: hover.y } : { x: 0, y: 0 }}
        transition={{ type: "spring", stiffness: 220, damping: 15 }}
      >
        {/* 3. breath: a slow, small drift so the overlap never sits perfectly still */}
        <motion.g
          animate={reduce ? { x: 0, y: 0 } : { x: [0, drift.x, 0], y: [0, drift.y, 0] }}
          transition={{ duration: 5.2, repeat: Infinity, ease: "easeInOut", delay: delay + 1.3 }}
        >
          <path d={d} fill={fill} style={blend ? { mixBlendMode: "multiply" } : undefined} />
        </motion.g>
      </motion.g>
    </motion.g>
  );
}

export default function CoherentLockup({ className = "" }: { className?: string }) {
  const reduce = !!useReducedMotion();
  const [hovered, setHovered] = useState(false);

  return (
    <div
      className={`relative flex items-start ${className}`}
      style={{ aspectRatio: `${LOCKUP_W} / ${LOGO_H}` }}
      onPointerEnter={() => setHovered(true)}
      onPointerLeave={() => setHovered(false)}
      aria-hidden="true"
    >
      <svg
        viewBox={`${ICON.x} ${ICON.y} ${ICON.w} ${ICON.h}`}
        style={{ width: pct(ICON.w), height: "auto", marginTop: pct(ICON_TOP), overflow: "visible", isolation: "isolate" }}
      >
        <Piece d={LIGHT} fill="#B6CDFB" from={{ x: -26, y: 26 }} drift={{ x: -2.5, y: 2.5 }} hover={{ x: -10, y: 10 }} delay={0.1} hovered={hovered} reduce={reduce} />
        <Piece d={BRIGHT} fill="#016DFD" from={{ x: 26, y: -26 }} drift={{ x: 2.5, y: -2.5 }} hover={{ x: 10, y: -10 }} delay={0.24} hovered={hovered} reduce={reduce} blend />
      </svg>
      <motion.div
        initial={reduce ? false : { clipPath: "inset(0 100% 0 0)", x: -6 }}
        animate={{ clipPath: "inset(0 0% 0 0)", x: 0 }}
        transition={{ duration: 0.8, ease: [0.2, 0.7, 0.2, 1], delay: 0.42 }}
        style={{
          width: pct(WORD_W),
          marginLeft: pct(WORD_X - ICON_LEFT - ICON.w),
          aspectRatio: `${WORD_W} / ${LOGO_H}`,
          backgroundImage: "url(/coherent-logo.png)",
          backgroundSize: `${(LOGO_W / WORD_W) * 100}% auto`,
          backgroundPosition: "right center",
          backgroundRepeat: "no-repeat",
        }}
      />
    </div>
  );
}
