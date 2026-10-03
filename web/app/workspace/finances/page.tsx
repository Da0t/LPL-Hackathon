"use client";
import { useState, useEffect } from "react";
import {
  Plus,
  ArrowUpRight,
  Pencil,
  WalletCards,
  X,
  Save,
  Search,
} from "lucide-react";
import { useClient, PageHeading } from "@/components/portal/shell";
import { Fields, FieldSpec } from "@/components/portal/fields";
import {
  Account,
  Client,
  accountTypes,
  money,
  title,
  portalApi,
} from "@/lib/portal";
const accountFields: FieldSpec[] = [
  ["familiar_label", "Account nickname"],
  ["custodian", "Institution / custodian"],
  ["last4", "Account number · last 4"],
  [
    "ownership",
    "Ownership",
    "text",
    ["individual", "joint", "trust", "custodial"],
  ],
  ["balance", "Total account value (USD)", "number"],
  ["cash_balance", "Cash portion (USD)", "number"],
  ["cost_basis", "Investment cost basis (USD)", "number"],
  ["balance_as_of", "Balance as of", "date"],
  ["opened_date", "Opened on", "date"],
  ["contributions_ytd", "Contributions year to date (USD)", "number"],
  ["distributions_ytd", "Distributions year to date (USD)", "number"],
  ["employer_match_ytd", "Employer match year to date (USD)", "number"],
  ["beneficiary", "Beneficiary name"],
  ["beneficiary_relationship", "Beneficiary relationship"],
  ["beneficiary_share", "Beneficiary share (%)", "number"],
  [
    "dividend_election",
    "Dividend election",
    "text",
    ["Reinvest", "Pay to cash"],
  ],
  ["investment_objective", "Investment objective"],
  [
    "risk_tolerance",
    "Risk preference",
    "text",
    ["Conservative", "Moderate", "Growth-oriented"],
  ],
  ["employer", "Employer / plan sponsor"],
];
const emptyAccount = {
  familiar_label: "",
  account_type: "brokerage",
  last4: "",
  custodian: "",
  ownership: "individual",
  balance: 0,
  cash_balance: 0,
  cost_basis: 0,
  balance_as_of: "2026-10-03",
  opened_date: "2026-01-01",
  contributions_ytd: 0,
  distributions_ytd: 0,
  employer_match_ytd: 0,
  beneficiary: "",
  beneficiary_relationship: "",
  beneficiary_share: 100,
  dividend_election: "Reinvest",
  investment_objective: "",
  risk_tolerance: "Moderate",
  employer: "",
};
export default function Finances() {
  const { client, setClient } = useClient();
  const [selected, setSelected] = useState(client.accounts[0].account_id),
    [tab, setTab] = useState("holdings"),
    [query, setQuery] = useState(""),
    [kind, setKind] = useState("all"),
    [editing, setEditing] = useState<string | null>(null),
    [recording, setRecording] = useState(false),
    [form, setForm] = useState<Record<string, any>>(emptyAccount),
    [activity, setActivity] = useState({
      account_id: selected,
      date: "2026-10-02",
      type: "deposit",
      description: "",
      amount: 0,
      related_account_id: "",
    }),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get("account");
    if (id && client.accounts.some((a) => a.account_id === id)) setSelected(id);
  }, []);
  const account = client.accounts.find((a) => a.account_id === selected)!;
  const history = client.activity.filter(
    (e) =>
      e.account_id === selected &&
      (kind === "all" || e.type === kind) &&
      e.description.toLowerCase().includes(query.toLowerCase()),
  );
  function edit(a?: Account) {
    setEditing(a?.account_id || "new");
    setError("");
    setForm(
      a
        ? Object.fromEntries(
            Object.keys(emptyAccount).map((k) => [
              k,
              k === "last4"
                ? a.masked_identifier.slice(-4)
                : (a[k] ?? (emptyAccount as any)[k]),
            ]),
          )
        : { ...emptyAccount },
    );
  }
  async function saveAccount(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const doc = await portalApi<Client>(
        "/portal/accounts" + (editing === "new" ? "" : "/" + editing),
        editing === "new" ? "POST" : "PUT",
        { revision: client.revision, account: form },
      );
      setClient(doc);
      setEditing(null);
      setNotice(
        "Account information saved as client-entered. Holdings need separate verification.",
      );
      if (editing === "new") setSelected(doc.accounts.at(-1)!.account_id);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="FINANCIAL PICTURE"
        title="More than a balance."
        description="Your investments, account details, and the history that connects them."
        action={
          <button className="portal-primary" onClick={() => edit()}>
            <Plus size={18} />
            Add an account
          </button>
        }
      />
      {notice && (
        <p className="portal-success" role="status">
          {notice}
        </p>
      )}
      <div className="finance-layout">
        <aside className="account-list">
          <p className="portal-eyebrow">
            YOUR ACCOUNTS · {client.accounts.length}
          </p>
          {client.accounts.map((a) => (
            <button
              key={a.account_id}
              className={selected === a.account_id ? "selected" : ""}
              onClick={() => {
                setSelected(a.account_id);
                setKind("all");
                setQuery("");
              }}
            >
              <span>
                {accountTypes[a.account_type] || a.account_type}
                <small>{a.familiar_label}</small>
              </span>
              <strong>{money(a.balance)}</strong>
              <small>{a.masked_identifier}</small>
            </button>
          ))}
        </aside>
        <div className="account-detail">
          <section className="portal-card">
            <div className="card-heading">
              <div>
                <p className="portal-eyebrow">
                  {accountTypes[account.account_type]} ·{" "}
                  {account.masked_identifier}
                </p>
                <h2>{account.familiar_label}</h2>
                <p>{account.custodian}</p>
              </div>
              <button
                className="portal-secondary"
                onClick={() => edit(account)}
              >
                <Pencil size={15} />
                Edit details
              </button>
            </div>
            <div className="account-balance">
              <strong>{money(account.balance)}</strong>
              <span>Recorded value · {account.balance_as_of}</span>
            </div>
            <div className="account-metrics">
              <div>
                <small>Cash balance</small>
                <b>{money(account.cash_balance)}</b>
              </div>
              <div>
                <small>Investment cost basis</small>
                <b>{money(account.cost_basis)}</b>
              </div>
              <div>
                <small>Contributions YTD</small>
                <b>{money(account.contributions_ytd)}</b>
              </div>
              <div>
                <small>Distributions YTD</small>
                <b>{money(account.distributions_ytd)}</b>
              </div>
            </div>
            <p className="record-source">
              {account.source} · {account.source_id} · Values are snapshots, not
              confirmation of funds available to withdraw.
            </p>
          </section>
          <div
            className="portal-tabs"
            role="tablist"
            aria-label="Account information"
          >
            {["holdings", "history", "details"].map((t) => (
              <button
                role="tab"
                aria-selected={tab === t}
                key={t}
                onClick={() => setTab(t)}
              >
                {t === "history" ? "Activity & history" : title(t)}
              </button>
            ))}
          </div>
          <section className="portal-card">
            {tab === "holdings" ? (
              <>
                <div className="card-heading">
                  <div>
                    <h2>What’s in this account</h2>
                    <p>
                      Fictional positions valued as of {account.balance_as_of}.
                    </p>
                  </div>
                </div>
                <div className="table-scroll">
                  <table className="portal-table">
                    <thead>
                      <tr>
                        <th>Investment</th>
                        <th>Shares</th>
                        <th>Price</th>
                        <th>Value</th>
                      </tr>
                    </thead>
                    <tbody>
                      {account.holdings.map((h) => (
                        <tr key={h.symbol}>
                          <td>
                            <strong>{h.name}</strong>
                            <small>
                              {h.symbol} · {h.asset_class}
                            </small>
                          </td>
                          <td>{h.quantity.toLocaleString()}</td>
                          <td>{money(h.price)}</td>
                          <td>{money(h.market_value)}</td>
                        </tr>
                      ))}
                      <tr>
                        <td>
                          <strong>Cash & equivalents</strong>
                          <small>Recorded cash portion</small>
                        </td>
                        <td>—</td>
                        <td>—</td>
                        <td>{money(account.cash_balance)}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                {account.source_kind === "self_reported" && (
                  <p className="profile-note">{account.holdings_note}</p>
                )}
              </>
            ) : tab === "history" ? (
              <>
                <div className="card-heading">
                  <div>
                    <h2>Account activity</h2>
                    <p>Transfers, contributions, and the moments in between.</p>
                  </div>
                  <button
                    className="portal-secondary"
                    onClick={() => {
                      setRecording(true);
                      setError("");
                      setActivity((a) => ({ ...a, account_id: selected }));
                    }}
                  >
                    <Plus size={16} />
                    Record past activity
                  </button>
                </div>
                <div className="history-filters">
                  <label>
                    <span className="sr-only">Search activity</span>
                    <input
                      placeholder="Search history…"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                    />
                  </label>
                  <label>
                    <span className="sr-only">Activity type</span>
                    <select
                      value={kind}
                      onChange={(e) => setKind(e.target.value)}
                    >
                      <option value="all">All activity types</option>
                      {Array.from(
                        new Set(
                          client.activity
                            .filter((e) => e.account_id === selected)
                            .map((e) => e.type),
                        ),
                      ).map((t) => (
                        <option key={t} value={t}>
                          {title(t)}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <div className="table-scroll">
                  <table className="portal-table">
                    <thead>
                      <tr>
                        <th>Date / settlement</th>
                        <th>Description & source</th>
                        <th>Amount</th>
                        <th>Account value after</th>
                      </tr>
                    </thead>
                    <tbody>
                      {history.map((e) => (
                        <tr key={e.event_id}>
                          <td>
                            {e.date}
                            <small>
                              {e.settlement_date || "Settlement not recorded"}
                            </small>
                          </td>
                          <td>
                            <strong>{e.description}</strong>
                            <small>
                              {title(e.type)} · {title(e.status)}
                            </small>
                            <small>{e.source_id}</small>
                          </td>
                          <td>{money(e.amount)}</td>
                          <td>
                            {e.balance_after == null
                              ? "Not recalculated"
                              : money(e.balance_after)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {!history.length && (
                    <p className="empty-state">
                      No activity matches these filters.
                    </p>
                  )}
                </div>
              </>
            ) : (
              <>
                <h2>Account details</h2>
                <dl className="detail-grid">
                  {[
                    ["Account type", accountTypes[account.account_type]],
                    ["Registration", title(account.ownership)],
                    ["Opened", account.opened_date],
                    ["Beneficiary", account.beneficiary || "Not recorded"],
                    [
                      "Relationship",
                      account.beneficiary_relationship || "Not recorded",
                    ],
                    ["Beneficiary share", `${account.beneficiary_share}%`],
                    ["Dividend preference", account.dividend_election],
                    ["Objective", account.investment_objective],
                    ["Risk preference", account.risk_tolerance],
                    ["Employer match YTD", money(account.employer_match_ytd)],
                    [
                      "Tax treatment",
                      account.tax_treatment || "Discuss with your advisor",
                    ],
                    ["Source", account.source],
                  ].map(([k, v]) => (
                    <div key={k}>
                      <dt>{k}</dt>
                      <dd>{v}</dd>
                    </div>
                  ))}
                </dl>
              </>
            )}
          </section>
        </div>
      </div>
      {editing && (
        <div className="portal-modal-backdrop">
          <section
            className="portal-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Account information"
          >
            <form onSubmit={saveAccount}>
              <div className="card-heading">
                <div>
                  <h2>
                    {editing === "new"
                      ? "Add an account"
                      : "Edit account information"}
                  </h2>
                  <p>
                    This records information; it does not open or change a
                    financial account.
                  </p>
                </div>
                <button
                  type="button"
                  aria-label="Close account editor"
                  className="icon-button"
                  onClick={() => setEditing(null)}
                >
                  <X />
                </button>
              </div>
              <label>
                Account type
                <select
                  value={form.account_type}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, account_type: e.target.value }))
                  }
                >
                  {Object.entries(accountTypes).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </label>
              <Fields
                fields={accountFields}
                values={form}
                onChange={(k, v) => setForm((f) => ({ ...f, [k]: v }))}
              />
              {error && (
                <p className="portal-error" role="alert">
                  {error}
                </p>
              )}
              <div className="form-footer">
                <span>Saved as client-entered information.</span>
                <button className="portal-primary" disabled={busy}>
                  {busy ? "Saving…" : "Save account"}
                </button>
              </div>
            </form>
          </section>
        </div>
      )}
      {recording && (
        <div className="portal-modal-backdrop">
          <section
            className="portal-modal compact"
            role="dialog"
            aria-modal="true"
            aria-label="Record past activity"
          >
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                setBusy(true);
                setError("");
                try {
                  setClient(
                    await portalApi<Client>("/portal/activity", "POST", {
                      revision: client.revision,
                      ...activity,
                      related_account_id: activity.related_account_id || null,
                    }),
                  );
                  setRecording(false);
                  setNotice(
                    "Historical activity saved as client-reported. No funds moved or balances changed.",
                  );
                } catch (e: any) {
                  setError(e.message);
                } finally {
                  setBusy(false);
                }
              }}
            >
              <div className="card-heading">
                <h2>Record past activity</h2>
                <button
                  type="button"
                  className="icon-button"
                  aria-label="Close activity form"
                  onClick={() => setRecording(false)}
                >
                  <X />
                </button>
              </div>
              <p className="profile-note">
                Add an activity you want your advisor to know about. This never
                executes a trade or transfer.
              </p>
              <Fields
                fields={[
                  ["date", "Activity date", "date"],
                  [
                    "type",
                    "Activity type",
                    "text",
                    [
                      "deposit",
                      "withdrawal",
                      "transfer",
                      "purchase",
                      "sale",
                      "dividend",
                      "interest",
                      "fee",
                      "contribution",
                      "rollover",
                      "distribution",
                      "beneficiary_update",
                    ],
                  ],
                  ["amount", "Amount (USD)", "number"],
                  ["description", "What happened?", "textarea"],
                ]}
                values={activity}
                onChange={(k, v) => setActivity((a) => ({ ...a, [k]: v }))}
              />
              {activity.type === "transfer" && (
                <label>
                  Transferred to
                  <select
                    required
                    value={activity.related_account_id}
                    onChange={(e) =>
                      setActivity((a) => ({
                        ...a,
                        related_account_id: e.target.value,
                      }))
                    }
                  >
                    <option value="">Choose an account</option>
                    {client.accounts
                      .filter((a) => a.account_id !== selected)
                      .map((a) => (
                        <option key={a.account_id} value={a.account_id}>
                          {a.familiar_label}
                        </option>
                      ))}
                  </select>
                </label>
              )}
              {error && (
                <p className="portal-error" role="alert">
                  {error}
                </p>
              )}
              <button className="portal-primary" disabled={busy}>
                {busy ? "Saving…" : "Save historical activity"}
              </button>
            </form>
          </section>
        </div>
      )}
    </>
  );
}
