export type Activity = {
  event_id: string;
  source_id: string;
  account_id: string;
  date: string;
  settlement_date: string | null;
  type: string;
  description: string;
  amount: number;
  currency: string;
  status: string;
  counterparty: string | null;
  value_change: number | null;
  balance_after: number | null;
};
export type Holding = {
  symbol: string;
  name: string;
  asset_class: string;
  quantity: number;
  price: number;
  market_value: number;
  cost_basis: number;
};
export type Account = {
  account_id: string;
  client_id: string;
  account_type: string;
  familiar_label: string;
  masked_identifier: string;
  balance: number;
  cash_balance: number;
  cost_basis: number;
  balance_as_of: string;
  source: string;
  source_kind: string;
  source_id: string;
  holdings: Holding[];
  [key: string]: any;
};
export type Client = {
  client_id: string;
  display_name: string;
  email: string;
  revision: number;
  profile: Record<string, any>;
  accounts: Account[];
  activity: Activity[];
  as_of: string;
  synthetic_only: boolean;
};
export type RequestDocument = {
  client_id: string;
  client_name: string;
  case_id: string | null;
  created_at: string;
  original_words: string;
  request_description: string;
  amount_requested: number | null;
  account: Account | null;
  history: Activity[];
  status: string;
  synthetic_only: boolean;
};
export async function portalApi<T = any>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch("/api" + path, {
      method,
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    });
  } catch {
    throw new Error(
      "The service could not be reached. Your changes are still here.",
    );
  }
  const data = await response.json();
  if (!response.ok) {
    if (
      response.status === 401 &&
      path != "/auth/login" &&
      typeof window !== "undefined"
    )
      window.location.assign("/login");
    throw new Error(
      data.message ||
        (data.error_code === "VALIDATION_ERROR"
          ? "Please check your fields and try again."
          : "The request could not be completed."),
    );
  }
  return data;
}
export const money = (n: number | undefined | null) =>
  n == null
    ? "Not stated"
    : new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 2,
      }).format(n);
export const title = (text: string) =>
  text.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
export const accountTypes: Record<string, string> = {
  brokerage: "Individual brokerage",
  joint_brokerage: "Joint brokerage",
  roth_ira: "Roth IRA",
  traditional_ira: "Traditional IRA",
  rollover_ira: "Rollover IRA",
  "401k": "401(k)",
  "403b": "403(b)",
  "457b": "457(b)",
  sep_ira: "SEP IRA",
  simple_ira: "SIMPLE IRA",
  hsa: "Health savings (HSA)",
  "529": "529 education savings",
  trust: "Trust account",
  cash_management: "Cash management",
  savings: "Savings",
  cd: "Certificate of deposit",
};
