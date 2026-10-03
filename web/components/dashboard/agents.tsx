"use client";

import React, { useEffect, useState } from "react";
import { Ear, Compass, BookOpen, Hammer, ShieldCheck, type LucideIcon } from "lucide-react";

// The Coherent agent team , each a Bedrock-powered specialist with a bit of
// personality. Every agent maps to a real task the backend already runs.
export type Agent = {
  id: "iris" | "atlas" | "sage" | "forge" | "sentinel";
  name: string;
  role: string;
  icon: LucideIcon;
  from: string;
  to: string;
  tagline: string;   // the character's voice
  does: string;      // what it actually does
  output: string;    // which output surface it owns
};

export const AGENTS: Agent[] = [
  {
    id: "iris", name: "Iris", role: "Intake", icon: Ear, from: "#38d6f0", to: "#0ea5e9",
    tagline: "Say it however it comes out , I'll make it make sense.",
    does: "Turns a client's plain words into a clear, account-grounded request.",
    output: "interpretation",
  },
  {
    id: "atlas", name: "Atlas", role: "Triage & routing", icon: Compass, from: "#8b96ff", to: "#5b63f0",
    tagline: "Give me the gist , I'll point it at exactly the right person.",
    does: "Classifies the request and finds the right advisor , or the security queue.",
    output: "routing",
  },
  {
    id: "sage", name: "Sage", role: "Advisor brief", icon: BookOpen, from: "#fcc34d", to: "#f59e0b",
    tagline: "I get the advisor ready so the first conversation actually counts.",
    does: "Writes the advisor prep brief: talking points, what to confirm, cautions.",
    output: "brief",
  },
  {
    id: "forge", name: "Forge", role: "Action prep", icon: Hammer, from: "#4f9bff", to: "#1677ff",
    tagline: "I prep the whole action. You just say go.",
    does: "Pre-fills the action end-to-end so a human only has to approve it.",
    output: "plan",
  },
  {
    id: "sentinel", name: "Sentinel", role: "Compliance", icon: ShieldCheck, from: "#4ade9f", to: "#10b981",
    tagline: "I check everything twice , no advice slips, no surprises.",
    does: "Runs identity, suitability, and no-advice checks and flags the risks.",
    output: "compliance",
  },
];

export const AGENT_BY_ID = Object.fromEntries(AGENTS.map((a) => [a.id, a])) as Record<Agent["id"], Agent>;

export type AgentStatus = "idle" | "working" | "done";

// Clean gradient avatar with the agent's role icon. If polished character art is
// dropped at /public/agents/<id>.png it is used automatically instead.
export function AgentAvatar({ agent, size = 40, className = "" }: { agent: Agent; size?: number; className?: string }) {
  const Icon = agent.icon;
  const [png, setPng] = useState(false);
  useEffect(() => {
    const img = new window.Image();
    img.onload = () => setPng(true);
    img.onerror = () => setPng(false);
    img.src = `/agents/${agent.id}.png`;
  }, [agent.id]);

  if (png) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={`/agents/${agent.id}.png`} alt={agent.name} width={size} height={size}
      className={`flex-none rounded-2xl object-cover ${className}`} />;
  }
  return (
    <span
      className={`grid flex-none place-items-center rounded-2xl text-white shadow-sm ${className}`}
      style={{ width: size, height: size, background: `linear-gradient(135deg, ${agent.from}, ${agent.to})` }}
      aria-hidden="true"
    >
      <Icon style={{ width: size * 0.5, height: size * 0.5 }} strokeWidth={2.2} />
    </span>
  );
}
