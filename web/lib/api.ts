// Coherent API client , talks to the live FastAPI + Amazon Bedrock backend.
// The backend enforces the frozen v1 contract; roles are simulated via headers.

export const API_BASE =
  process.env.NEXT_PUBLIC_SAMEPAGE_API || "http://127.0.0.1:8000";

export type Suggestion = { id: string; label: string; account_id?: string };
export type Definition = { term: string; plain: string };

export type TurnResponse = {
  session_id: string;
  transcript: string;
  suggestions: Suggestion[];
  question: string | null;
  definitions: Definition[];
  candidate_intent: string | null;
  selected_account_id: string | null;
  uncertainty: string | null;
  status: string;
  degraded?: boolean;
  message?: string;
};

export type CaseRow = {
  case_id: string;
  client_display_name: string;
  created_at: string;
  status: string;
  categories: string[];
  flags: string[];
  confirmed_plain_language_request: string;
  routing?: { destination?: string; assigned_advisor_id?: string | null };
  urgency?: { level?: string };
  priority?: Priority;
  lifecycle?: Lifecycle;
  intake?: { turns: number; seconds_to_confirm: number } | null;
};
export type Priority = { level: "urgent" | "high" | "normal" | "low" | "done"; rank: number; reason: string };
export type Lifecycle = "new" | "awaiting_client" | "assigned" | "scheduled" | "resolved";

export type Candidate = {
  advisor_id: string;
  display_name: string;
  specialties: string[];
  available: boolean;
  reason: string;
  existing_client_relationship?: boolean;
  meeting_mode?: string[];
  capacity?: number;
};

export class ApiError extends Error {
  code: string;
  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

async function call<T>(
  path: string,
  opts: { method?: string; body?: unknown; role: "client" | "staff"; clientId?: string } = { role: "client" },
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Demo-Role": opts.role,
  };
  if (opts.clientId) headers["X-Demo-Client-Id"] = opts.clientId;
  let res: Response;
  try {
    res = await fetch(API_BASE + path, {
      method: opts.method || "GET",
      headers,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    });
  } catch {
    throw new ApiError("NETWORK", "Could not reach the Coherent service.");
  }
  let data: any = null;
  try {
    data = await res.json();
  } catch {
    if (!res.ok) throw new ApiError("BAD_RESPONSE", "The service returned an unreadable response.");
  }
  if (!res.ok) {
    throw new ApiError(data?.error_code || "ERROR", data?.message || "Request failed.");
  }
  return data as T;
}

// ---- Client intake ----
export const startIntake = (clientId: string) =>
  call<{ session_id: string; client_display_name: string; status: string }>("/intake/start", {
    method: "POST", role: "client", clientId, body: { client_id: clientId },
  });

export const intakeTurn = (
  sessionId: string, clientId: string,
  payload: { text: string; input_mode: "text" | "voice"; selected_option_id?: string | null },
) =>
  call<TurnResponse>(`/intake/${encodeURIComponent(sessionId)}/turn`, {
    method: "POST", role: "client", clientId, body: payload,
  });

export const confirmIntake = (
  sessionId: string, clientId: string,
  payload: { confirmed_plain_language_request: string; selected_account_id?: string | null; amount_requested?: number | null },
) =>
  call<{ case_id: string; status: string; client_summary: string }>(`/intake/${encodeURIComponent(sessionId)}/confirm`, {
    method: "POST", role: "client", clientId, body: payload,
  });

export const getDemoClients = () =>
  call<{ clients: { client_id: string; display_name: string }[] }>("/demo/clients", { role: "client" });

// ---- The client's own requests after intake ----
export type MyRequest = {
  case_id: string; created_at: string; request: string; lifecycle: Lifecycle; awaiting_reply: boolean;
  messages: { from: "advisor" | "client"; text: string; at: string }[];
};
export const getMyRequests = (clientId: string) =>
  call<{ requests: MyRequest[] }>("/my/requests", { role: "client", clientId });
export const replyToRequest = (clientId: string, caseId: string, text: string) =>
  call<MyRequest>(`/my/requests/${encodeURIComponent(caseId)}/reply`, { method: "POST", role: "client", clientId, body: { text } });

// ---- Staff ----
export const getCases = () => call<{ cases: CaseRow[] }>("/staff/cases", { role: "staff" });
export const getCase = (id: string) => call<any>(`/staff/cases/${encodeURIComponent(id)}`, { role: "staff" });
export const getCandidates = (id: string) =>
  call<{ candidates: Candidate[]; destination?: string; reason?: string }>(`/staff/cases/${encodeURIComponent(id)}/candidates`, { role: "staff" });
export const assignCase = (id: string, advisor_id: string, staff_reason: string) =>
  call<{ case_id: string; status: string; assigned_advisor_id: string }>(`/staff/cases/${encodeURIComponent(id)}/assign`, {
    method: "POST", role: "staff", body: { advisor_id, staff_reason },
  });

export type Brief = {
  case_id: string; ai_mode: string; note: string | null;
  headline: string; talking_points: string[]; confirm: string[]; cautions: string[];
};
// Agent endpoints reuse their last answer for an unchanged case; `refresh` asks for a new one.
export const getBrief = (id: string, refresh = false) =>
  call<Brief>(`/staff/cases/${encodeURIComponent(id)}/brief`, { method: "POST", role: "staff", body: { refresh } });

export type AdvisorAction = "claim" | "note" | "clarify" | "schedule" | "resolve" | "approve" | "escalate";
// The server re-checks a message itself before sending; only `override` is honoured from here.
export type SentCompliance = { verdict: "pass" | "needs_changes"; override: boolean };
export const caseAction = (id: string, action: AdvisorAction, text?: string, compliance?: SentCompliance, acknowledgedFlags?: string[]) =>
  call<{ case_id: string; status: string; event: { event: string; at: string; details: Record<string, unknown> } }>(
    `/staff/cases/${encodeURIComponent(id)}/action`,
    { method: "POST", role: "staff", body: { action, text, compliance, acknowledged_flags: acknowledgedFlags } });

export type ActionPlan = {
  case_id: string; ai_mode: string; note: string | null;
  headline: string; action_type: string;
  prepared_fields: { label: string; value: string }[];
  compliance_checks: { item: string; status: "pass" | "review" | "flag"; note?: string }[];
  draft_client_message: string; draft_advisor_followup: string;
};
export const getPlan = (id: string) =>
  call<ActionPlan>(`/staff/cases/${encodeURIComponent(id)}/plan`, { method: "POST", role: "staff" });

// ---- Advisor agents: reply drafter + compliance reviewer ----
export type ComplianceCheck = { id: string; label: string; status: "pass" | "attention"; evidence: string };
export type ComplianceFinding = { quote: string; issue: string; suggestion: string };
export type ComplianceReview = {
  verdict: "pass" | "needs_changes"; checks: ComplianceCheck[]; findings: ComplianceFinding[];
  ai_mode?: string; note?: string | null;
};
export type AgentTraceStep = { agent: "drafter" | "compliance"; step: string; summary: string };
export type ReplyDraft = {
  case_id: string; ai_mode: string; note: string | null;
  draft: string; review: ComplianceReview; revised: boolean; trace: AgentTraceStep[];
};
export const draftReply = (id: string, instruction?: string) =>
  call<ReplyDraft>(`/staff/cases/${encodeURIComponent(id)}/reply-draft`, { method: "POST", role: "staff", body: { instruction } });
export const complianceReview = (id: string, draft?: string) =>
  call<ComplianceReview>(`/staff/cases/${encodeURIComponent(id)}/compliance-review`, { method: "POST", role: "staff", body: { draft } });

// ---- Advisor agents: next-steps planner + fraud investigator ----
export type PlanStep = { title: string; detail: string; owner: "advisor" | "client" | "operations" };
export type NextSteps = { case_id: string; ai_mode: string; note: string | null; summary: string; steps: PlanStep[] };
export const getNextSteps = (id: string, refresh = false) =>
  call<NextSteps>(`/staff/cases/${encodeURIComponent(id)}/next-steps`, { method: "POST", role: "staff", body: { refresh } });

export type TimelineEntry = {
  date: string; type: string; label: string; detail: string; account: string | null; source_id: string; highlight: boolean;
};
export type Investigation = {
  case_id: string; ai_mode: string; note: string | null;
  risk_level: "low" | "medium" | "high"; reasons: string[]; recommended_steps: string[]; timeline: TimelineEntry[];
};
export const getInvestigation = (id: string, refresh = false) =>
  call<Investigation>(`/staff/cases/${encodeURIComponent(id)}/investigation`, { method: "POST", role: "staff", body: { refresh } });

// ---- Client snapshot (records only, no model) ----
export type AdvisorRef = { advisor_id: string; display_name: string };
export type ClientSnapshot = {
  case_id: string;
  client: { client_id: string; display_name: string; preferred_contact_channel?: string | null; meeting_preference?: string | null; state?: string | null };
  usual_advisor: AdvisorRef | null;
  assigned_advisor: AdvisorRef | null;
  accounts: { account_id: string; label: string; familiar_label?: string | null; masked_identifier: string; balance: number | null; balance_as_of?: string | null; is_case_account: boolean }[];
  recent_events: { date: string; type: string; summary: string; account_label: string; masked_identifier: string; source_id: string }[];
  other_cases: CaseRow[];
};
export const getClientSnapshot = (id: string) =>
  call<ClientSnapshot>(`/staff/cases/${encodeURIComponent(id)}/client`, { role: "staff" });

export const health = () => call<any>("/health", { role: "client" });

// ---- Friendly labels ----
export const CATEGORY_LABELS: Record<string, string> = {
  retirement_income: "Retirement income",
  withdrawal_or_distribution: "Withdrawal / distribution",
  rollover_or_transfer: "Rollover / transfer",
  beneficiary_or_estate: "Beneficiary / estate",
  investment_planning: "Investment planning",
  account_service: "Account service",
  fraud_or_security: "Fraud / security",
  other_or_unclear: "Other / unclear",
};
export const prettyCategory = (c: string) => CATEGORY_LABELS[c] || c.replace(/_/g, " ");
