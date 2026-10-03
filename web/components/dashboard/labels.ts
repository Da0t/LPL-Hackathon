// Plain-language labels for the advisor dashboard. Raw codes never reach the screen.
import type { Lifecycle, Priority } from "@/lib/api";

export function timeAgo(iso: string): string {
  const t = Date.parse(iso);
  if (isNaN(t)) return "";
  const s = Math.max(0, (Date.now() - t) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export function prettyDate(date: string): string {
  const d = new Date(date.length === 10 ? `${date}T00:00:00` : date);
  return isNaN(d.getTime()) ? date : d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export const sentence = (code: string) => {
  const text = (code || "").replace(/_/g, " ").trim();
  return text.charAt(0).toUpperCase() + text.slice(1);
};

const STATUS: Record<string, string> = {
  submitted: "New", staff_review: "In review", assigned: "Assigned", needs_client_followup: "Waiting on client",
};
export const statusLabel = (status: string) => STATUS[status] || sentence(status);

const FLAGS: Record<string, string> = {
  client_term_did_not_match_account_type: "The client's wording didn't match the account on record",
  possible_unauthorized_access: "Possible unauthorized access",
  staff_overrode_recommendation: "Staff chose an advisor outside the recommendations",
  staff_overrode_specialist_recommendation: "Staff assigned an advisor instead of the security specialists",
};
export const flagLabel = (flag: string) => FLAGS[flag] || sentence(flag);

export const LIFECYCLE_LABELS: Record<Lifecycle, string> = {
  new: "New / In review", awaiting_client: "Waiting on client", assigned: "Assigned", scheduled: "Scheduled", resolved: "Resolved",
};

export const HISTORY_LABELS: Record<string, string> = {
  advisor_claimed: "Claimed by advisor", advisor_note: "Note added", clarification_requested: "Message sent to client",
  meeting_scheduled: "Meeting scheduled", request_resolved: "Resolved", assigned: "Assigned to an advisor",
  reassigned: "Reassigned", staff_review_started: "Opened for review", seeded: "Request received",
};

export const PRIORITY_DOT: Record<Priority["level"], string> = {
  urgent: "bg-red-500", high: "bg-amber-500", normal: "bg-primary", low: "bg-muted-foreground/50", done: "bg-emerald-500",
};
export const PRIORITY_TEXT: Record<Priority["level"], string> = {
  urgent: "text-red-600", high: "text-amber-700", normal: "text-foreground", low: "text-muted-foreground", done: "text-emerald-700",
};

export const money = (n: number) => `$${n.toLocaleString()}`;
