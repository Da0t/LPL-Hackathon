"use client";
import Link from "next/link";
import {
  ArrowUpRight,
  ArrowRight,
  Wallet,
  FileText,
  UserRound,
  ArrowDownLeft,
} from "lucide-react";
import { useClient, PageHeading } from "@/components/portal/shell";
import { money, accountTypes, title } from "@/lib/portal";
export default function Overview() {
  const { client } = useClient();
  const total = client.accounts.reduce((n, a) => n + a.balance, 0),
    cash = client.accounts.reduce((n, a) => n + a.cash_balance, 0);
  return (
    <>
      <PageHeading
        eyebrow="YOUR OVERVIEW"
        title="Everything, in perspective."
        description="A connected view of your accounts and the conversations ahead."
        action={
          <Link className="portal-primary" href="/workspace/requests/new">
            New request <ArrowUpRight size={18} />
          </Link>
        }
      />
      <div className="overview-stats">
        <div className="stat-card featured">
          <span>Total recorded assets</span>
          <strong>{money(total)}</strong>
          <small>
            Across {client.accounts.length} accounts · snapshots as of{" "}
            {client.as_of}
          </small>
          <div className="stat-spark">
            <svg viewBox="0 0 300 60" preserveAspectRatio="none">
              <path d="M0 58 L24 46 L52 50 L80 37 L104 41 L140 26 L164 33 L199 18 L230 24 L265 8 L300 1" />
            </svg>
          </div>
        </div>
        <div className="stat-card">
          <span>Recorded cash balance</span>
          <strong>{money(cash)}</strong>
          <small>Included in total assets · not withdrawal approval</small>
        </div>
        <div className="stat-card">
          <span>Accounts in view</span>
          <strong>{client.accounts.length.toString().padStart(2, "0")}</strong>
          <small>Retirement, investments, and everyday savings</small>
        </div>
      </div>
      <div className="overview-grid">
        <section className="portal-card">
          <div className="card-heading">
            <div>
              <h2>Your accounts</h2>
              <p>The familiar names behind your financial picture.</p>
            </div>
            <Link href="/workspace/finances">
              View all <ArrowRight size={16} />
            </Link>
          </div>
          {client.accounts.slice(0, 5).map((a) => (
            <Link
              href={"/workspace/finances?account=" + a.account_id}
              className="account-row"
              key={a.account_id}
            >
              <span className="account-icon">
                <Wallet size={20} />
              </span>
              <span>
                <strong>{a.familiar_label}</strong>
                <small>
                  {accountTypes[a.account_type] || title(a.account_type)} ·{" "}
                  {a.masked_identifier}
                </small>
              </span>
              <b>{money(a.balance)}</b>
              <ArrowUpRight size={17} />
            </Link>
          ))}
        </section>
        <section className="next-step-card">
          <div className="blue-icon">
            <FileText size={27} />
          </div>
          <p className="portal-eyebrow">A GOOD NEXT STEP</p>
          <h2>
            Something on
            <br />
            your mind?
          </h2>
          <p>
            Use your own words. We’ll help clarify your request and bring the
            relevant account details together.
          </p>
          <Link className="portal-primary" href="/workspace/requests/new">
            Start a conversation <ArrowRight size={18} />
          </Link>
          <Link className="subtle-link" href="/workspace/profile">
            <UserRound size={16} />
            Keep your profile up to date
          </Link>
        </section>
      </div>
      <section className="portal-card">
        <div className="card-heading">
          <div>
            <h2>Recent activity</h2>
            <p>A few of the latest entries in your account history.</p>
          </div>
          <Link href="/workspace/finances">
            Explore history <ArrowRight size={16} />
          </Link>
        </div>
        <div className="table-scroll">
          <table className="portal-table">
            <thead>
              <tr>
                <th>Activity</th>
                <th>Account</th>
                <th>Date</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {client.activity.slice(0, 5).map((e) => (
                <tr key={e.event_id}>
                  <td>
                    <strong>{e.description}</strong>
                    <small>{title(e.type)}</small>
                  </td>
                  <td>
                    {
                      client.accounts.find((a) => a.account_id === e.account_id)
                        ?.familiar_label
                    }
                  </td>
                  <td>{e.date}</td>
                  <td>{money(e.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
