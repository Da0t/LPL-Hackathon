"use client";
import React from "react";
import { motion, useReducedMotion } from "motion/react";

// One reveal per section. Used on section containers, not on every card.
export function Reveal({
  children,
  className = "",
  delay = 0,
  as = "div",
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
  as?: "div" | "section" | "li" | "header";
}) {
  const reduce = useReducedMotion();
  const Tag = motion[as];
  return (
    <Tag
      className={className}
      initial={reduce ? false : { opacity: 0, y: 22 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-12% 0px" }}
      transition={{ duration: 0.75, ease: [0.2, 0.7, 0.2, 1], delay }}
    >
      {children}
    </Tag>
  );
}
