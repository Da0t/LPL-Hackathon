export type AgentEvent = {
  type: string;
  agent?: string;
  text?: string;
  tool?: string;
  model?: string;
  message?: string;
  source_id?: string;
  verdict?: string;
  [key: string]: any;
};
export type AgentRun = {
  running: boolean;
  events: AgentEvent[];
  preview: string;
  diagnostics?: any;
  error?: string;
  auditVerdict?: string;
  tokenChunks?: number;
};
const runs = new Map<string, AgentRun>();
const listeners = new Set<() => void>();
export const runKey = (caseId: string, operation: string) =>
  caseId + ":" + operation;
export const readRun = (key: string) => runs.get(key);
export const subscribeRuns = (callback: () => void) => {
  listeners.add(callback);
  return () => {
    listeners.delete(callback);
  };
};
export function beginRun(key: string) {
  runs.set(key, { running: true, events: [], preview: "" });
  if (runs.size > 40) runs.delete(runs.keys().next().value!);
  listeners.forEach((l) => l());
}
export function updateRun(key: string, event: AgentEvent) {
  const old = runs.get(key);
  if (!old) return;
  const next = { ...old };
  if (event.type === "token") {
    next.preview = (next.preview + (event.text || "")).slice(-12000);
    next.tokenChunks = (old.tokenChunks || 0) + 1;
  } else if (event.type === "audit") next.auditVerdict = event.verdict;
  else if (event.type === "result") {
    next.running = false;
    next.diagnostics = event.result?.diagnostics;
    next.auditVerdict = event.result?.audit?.verdict || next.auditVerdict;
  } else if (event.type === "error") {
    next.running = false;
    next.error = event.message;
  } else if (event.type === "done") next.running = false;
  else if (event.type === "stage") {
    next.preview += `\n[${event.agent}]\n`;
    next.events = [...next.events, event].slice(-80);
  } else next.events = [...next.events, event].slice(-80);
  runs.set(key, next);
  listeners.forEach((l) => l());
}
