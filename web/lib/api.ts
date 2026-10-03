// Coherent API client , talks to the live FastAPI + Amazon Bedrock backend.
// The backend enforces the frozen v1 contract. Cognito cookies authorize portal calls;
// demo headers are supported only by the explicitly unconfigured legacy server.

export const API_BASE =
  process.env.NEXT_PUBLIC_SAMEPAGE_API || "/api";

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
};

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
      credentials: "include",
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
export const getBrief = (id: string) =>
  call<Brief>(`/staff/cases/${encodeURIComponent(id)}/brief`, { method: "POST", role: "staff" });

export type AdvisorAction = "claim" | "note" | "clarify" | "schedule" | "resolve";
export const caseAction = (id: string, action: AdvisorAction, text?: string) =>
  call<{ case_id: string; status: string; event: { event: string; at: string; details: Record<string, unknown> } }>(
    `/staff/cases/${encodeURIComponent(id)}/action`, { method: "POST", role: "staff", body: { action, text } });

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
