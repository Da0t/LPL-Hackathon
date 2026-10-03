"use client";
import { RequestDocument, money, accountTypes, title } from "@/lib/portal";
export function RequestPaper({ document: doc }: { document: RequestDocument }) {
  const a = doc.account;
  return (
    <article className="request-paper" aria-label="Request document">
      <header className="paper-header">
        <span className="paper-wordmark">
          coherent<span>●</span>
        </span>
        <span>
          CLIENT SERVICE REQUEST
          <br />
          <small>{doc.case_id || "DRAFT / NOT SENT"}</small>
        </span>
      </header>
      <div className="paper-title">
        <p>PREPARED FOR YOUR ADVISOR’S TEAM</p>
        <h2>{doc.client_name}</h2>
        <span>
          {doc.client_id} · {doc.created_at.slice(0, 10)}
        </span>
      </div>
      <section>
        <h3>01 / Request description</h3>
        <p className="paper-description">
          {doc.request_description ||
            "Your request will appear here as you describe what you need."}
        </p>
        <dl className="paper-values">
          <div>
            <dt>Amount to discuss</dt>
            <dd>{money(doc.amount_requested)}</dd>
          </div>
          <div>
            <dt>Status</dt>
            <dd>{doc.status}</dd>
          </div>
        </dl>
      </section>
      <section>
        <h3>02 / In your own words</h3>
        <blockquote>
          {doc.original_words || "Waiting for your words."}
        </blockquote>
      </section>
      <section>
        <h3>03 / Relevant account & exact values</h3>
        {a ? (
          <>
            <h4>{a.familiar_label}</h4>
            <p>
              {accountTypes[a.account_type] || title(a.account_type)} ·{" "}
              {a.masked_identifier}
            </p>
            <dl className="paper-values">
              {[
                ["Recorded account value", money(a.balance)],
                ["Cash portion", money(a.cash_balance)],
                ["Investment cost basis", money(a.cost_basis)],
                ["Contributions YTD", money(a.contributions_ytd)],
                ["Distributions YTD", money(a.distributions_ytd)],
                ["Employer match YTD", money(a.employer_match_ytd)],
                ["Beneficiary", a.beneficiary || "Not recorded"],
                [
                  "Beneficiary share",
                  a.beneficiary_share == null
                    ? "Not recorded"
                    : `${a.beneficiary_share}%`,
                ],
                ["Balance as of", a.balance_as_of],
                ["Record source", a.source || "Synthetic statement"],
              ].map(([k, v]) => (
                <div key={k}>
                  <dt>{k}</dt>
                  <dd>{v}</dd>
                </div>
              ))}
            </dl>
            <p className="paper-source">{a.source_id}</p>
            {a.holdings.length > 0 && (
              <>
                <h4>Recorded holdings</h4>
                <table>
                  <thead>
                    <tr>
                      <th>Investment</th>
                      <th>Shares</th>
                      <th>Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {a.holdings.map((h) => (
                      <tr key={h.symbol}>
                        <td>
                          {h.name}
                          <small>{h.symbol}</small>
                        </td>
                        <td>{h.quantity}</td>
                        <td>{money(h.market_value)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </>
        ) : (
          <p>No account selected. Your team can help clarify.</p>
        )}
      </section>
      <section>
        <h3>04 / Relevant account history</h3>
        {doc.history.length ? (
          <table>
            <thead>
              <tr>
                <th>Date / activity</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {doc.history.map((e) => (
                <tr key={e.event_id}>
                  <td>
                    <strong>{e.date}</strong>
                    <span>{e.description}</span>
                    <small>
                      {e.source_id} · {title(e.status)}
                    </small>
                  </td>
                  <td>{money(e.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p>No account history is attached until you select an account.</p>
        )}
      </section>
      <footer>
        <p>
          Account values are dated snapshots. This document is a request for
          discussion and does not authorize a transaction, appointment, or
          advisor assignment.
        </p>
        <span>Fictional records · Client-confirmed wording · Coherent</span>
      </footer>
    </article>
  );
}
