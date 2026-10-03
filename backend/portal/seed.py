"""Deterministic, entirely fictional client records. No real SSNs or securities."""

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AS_OF = "2026-10-03"


def make_profiles():
    clients = json.loads((ROOT / "data/clients.json").read_text())["clients"]
    accounts = json.loads((ROOT / "data/accounts.json").read_text())["accounts"]
    people = [
        (
            "mara.ellis@example.com",
            "1958-04-18",
            "Married",
            "Retired",
            "Mesa Learning Center",
            "Educator",
            "18 Juniper Lane",
            "Mesa",
            "AZ",
            "85201",
            78000,
            720000,
            9600,
            "Thomas Ellis",
            "Spouse",
            "Retirement income",
            "Conservative",
        ),
        (
            "evan.brooks@example.com",
            "1986-09-12",
            "Single",
            "Employed",
            "Cedar Systems",
            "Product designer",
            "204 Cypress Drive",
            "Austin",
            "TX",
            "78701",
            148000,
            435000,
            5800,
            "Nora Brooks",
            "Sister",
            "Long-term growth",
            "Moderate",
        ),
        (
            "lena.marchetti@example.com",
            "1969-02-26",
            "Married",
            "Self-employed",
            "Marchetti Studio",
            "Architect",
            "72 Laurel Court",
            "Pasadena",
            "CA",
            "91101",
            192000,
            1250000,
            7400,
            "Sofia Marchetti",
            "Daughter",
            "Legacy planning",
            "Moderate",
        ),
    ]
    extras = [
        [
            ("ACCT-203", "cash_management", "Household reserve", 18600, "3902"),
            ("ACCT-204", "529", "Education for our grandchildren", 26800, "1864"),
        ],
        [
            ("ACCT-304", "401k", "Cedar Systems workplace retirement", 126800, "4722"),
            ("ACCT-305", "hsa", "Health savings", 14250, "8006"),
            ("ACCT-306", "savings", "Emergency savings", 28500, "5503"),
        ],
        [
            ("ACCT-404", "sep_ira", "Studio retirement plan", 97500, "6783"),
            ("ACCT-405", "trust", "Family legacy trust", 168000, "2218"),
            ("ACCT-406", "529", "Sofia’s education fund", 32900, "9251"),
        ],
    ]
    output = []
    for idx, (client, values) in enumerate(zip(clients, people)):
        (
            email,
            birth,
            marital,
            employment,
            employer,
            occupation,
            street,
            city,
            state,
            zipcode,
            income,
            worth,
            expenses,
            contact,
            relation,
            objective,
            risk,
        ) = values
        own = copy.deepcopy(
            [a for a in accounts if a["client_id"] == client["client_id"]]
        )
        for aid, kind, label, balance, mask in extras[idx]:
            own.append(
                dict(
                    account_id=aid,
                    client_id=client["client_id"],
                    account_type=kind,
                    familiar_label=label,
                    balance=balance,
                    masked_identifier="****" + mask,
                    ownership="individual",
                    opened_date="2021-03-12",
                    currency="USD",
                    source_id="ACCOUNT-RECORD-" + aid,
                )
            )
        for n, a in enumerate(own):
            cash = round(
                a["balance"]
                * (
                    0.12
                    if a["account_type"] not in ("savings", "cash_management")
                    else 1
                ),
                2,
            )
            a.update(
                balance_as_of=AS_OF,
                custodian="Coherent Demo Custody",
                source="Synthetic statement",
                source_kind="statement",
                status="open",
                cash_balance=cash,
                cost_basis=round((a["balance"] - cash) * 0.84, 2),
                contributions_ytd=3000
                if "ira" in a["account_type"]
                else 5400
                if a["account_type"] == "401k"
                else 0,
                distributions_ytd=2400 if idx == 0 and n == 0 else 0,
                employer_match_ytd=2700 if a["account_type"] == "401k" else 0,
                tax_treatment="Taxable"
                if a["account_type"]
                in (
                    "brokerage",
                    "joint_brokerage",
                    "cash_management",
                    "savings",
                    "trust",
                )
                else "Tax-advantaged; rules depend on account type",
                beneficiary=contact,
                beneficiary_relationship=relation,
                beneficiary_share=100,
                dividend_election="Reinvest",
                investment_objective=objective,
                risk_tolerance=risk,
                employer=employer if a["account_type"] == "401k" else "",
                former_employer="Mesa Learning Center"
                if a["account_type"] == "rollover_ira"
                else "",
                contribution_tax_year=2026,
                statement_date=AS_OF,
            )
            invested = round(a["balance"] - cash, 2)
            a["holdings"] = (
                [
                    dict(
                        symbol="DEMO-EQ",
                        name="Fictional diversified equity fund",
                        asset_class="Equity",
                        quantity=round(invested * 0.6 / 100, 4),
                        price=100,
                        market_value=round(invested * 0.6, 2),
                        cost_basis=round(invested * 0.6 * 0.84, 2),
                    ),
                    dict(
                        symbol="DEMO-FI",
                        name="Fictional income fund",
                        asset_class="Fixed income",
                        quantity=round(invested * 0.4 / 50, 4),
                        price=50,
                        market_value=round(invested * 0.4, 2),
                        cost_basis=round(invested * 0.4 * 0.84, 2),
                    ),
                ]
                if invested
                else []
            )
        activity = []
        for n, a in enumerate(own):
            aid = a["account_id"]
            investment = bool(a["holdings"])
            templates = [
                (
                    "2026-01-08",
                    "contribution",
                    "Annual contribution"
                    if "ira" in a["account_type"]
                    else "Scheduled deposit",
                    1500,
                    1500,
                ),
                ("2026-03-15", "dividend", "Quarterly dividend", 126.75, 126.75),
                (
                    "2026-03-16",
                    "reinvestment",
                    "Dividend reinvestment · DEMO-EQ",
                    126.75,
                    0,
                ),
                ("2026-04-11", "purchase", "Purchase · DEMO-FI", 2000, 0),
                ("2026-05-20", "sale", "Sale · DEMO-EQ", 850, 0),
                ("2026-06-30", "fee", "Quarterly service fee", 35, -35),
                ("2026-07-15", "interest", "Cash interest", 24.80, 24.80),
                (
                    "2026-08-03",
                    "beneficiary_update",
                    "Beneficiary reviewed: " + contact,
                    0,
                    0,
                ),
                ("2026-09-04", "contribution", "Scheduled contribution", 1500, 1500),
                (
                    "2026-09-30",
                    "market_change",
                    "Statement market-value adjustment",
                    420.25,
                    420.25,
                ),
            ]
            if not investment:
                templates = [
                    t
                    for t in templates
                    if t[1]
                    not in (
                        "reinvestment",
                        "purchase",
                        "sale",
                        "dividend",
                        "market_change",
                    )
                ]
            if a["account_type"] == "rollover_ira":
                templates.insert(
                    0,
                    (
                        "2023-06-12",
                        "rollover",
                        "Rollover from former workplace plan",
                        72000,
                        72000,
                    ),
                )
            if a["account_type"] == "401k":
                templates.append(
                    (
                        "2026-09-30",
                        "employer_match",
                        "Employer matching contribution",
                        2700,
                        2700,
                    )
                )
            if idx == 0 and n == 0:
                templates.append(
                    (
                        "2026-08-12",
                        "distribution",
                        "Retirement distribution for household expenses",
                        2400,
                        -2400,
                    )
                )
            for k, (date, kind, description, amount, impact) in enumerate(templates):
                activity.append(
                    dict(
                        event_id=f"PORTAL-{aid}-{k:02}",
                        source_id=f"STATEMENT-{aid}-{date}",
                        account_id=aid,
                        date=date,
                        settlement_date=date,
                        type=kind,
                        description=description,
                        summary=description,
                        amount=amount,
                        value_change=impact,
                        currency="USD",
                        status="posted",
                        counterparty=None,
                    )
                )
        # Matched, within-client transfer legs; balances below reconcile exactly.
        taxable = next(
            a for a in own if a["account_type"] in ("brokerage", "joint_brokerage")
        )
        reserve = next(
            a for a in own if a["account_type"] in ("cash_management", "savings")
        )
        for a, impact, other in [(taxable, -1250, reserve), (reserve, 1250, taxable)]:
            activity.append(
                dict(
                    event_id="TRANSFER-" + a["account_id"],
                    source_id=f"TRANSFER-{client['client_id']}-001",
                    account_id=a["account_id"],
                    date="2026-09-18",
                    settlement_date="2026-09-19",
                    type="transfer_out" if impact < 0 else "transfer_in",
                    description="Internal transfer "
                    + ("to " if impact < 0 else "from ")
                    + other["familiar_label"],
                    summary="Matched internal transfer",
                    amount=1250,
                    value_change=impact,
                    currency="USD",
                    status="posted",
                    counterparty=other["account_id"],
                )
            )
        for a in own:
            ledger = sorted(
                [t for t in activity if t["account_id"] == a["account_id"]],
                key=lambda t: (t["date"], t["event_id"]),
            )
            running = round(a["balance"] - sum(t["value_change"] for t in ledger), 2)
            a["opening_value"] = running
            for t in ledger:
                running = round(running + t["value_change"], 2)
                t["balance_after"] = running
        output.append(
            dict(
                client_id=client["client_id"],
                display_name=client["display_name"],
                email=email,
                revision=1,
                profile=dict(
                    legal_name=client["display_name"],
                    preferred_name=client["display_name"].split()[0],
                    date_of_birth=birth,
                    ssn_last4=["4821", "6205", "3390"][idx],
                    phone=f"202-555-01{10 + idx}",
                    email=email,
                    street=street,
                    address_line2="",
                    city=city,
                    state=state,
                    postal_code=zipcode,
                    country="United States",
                    citizenship="United States",
                    tax_residency="United States",
                    marital_status=marital,
                    employment_status=employment,
                    employer=employer,
                    occupation=occupation,
                    trusted_contact=contact,
                    trusted_contact_relationship=relation,
                    trusted_contact_phone=f"202-555-01{20 + idx}",
                    preferred_contact=client["preferred_contact_channel"],
                    meeting_preference=client["meeting_preference"],
                    annual_income=income,
                    net_worth=worth,
                    liquid_net_worth=sum(a["balance"] for a in own),
                    monthly_expenses=expenses,
                    liabilities=48000 if idx != 1 else 96000,
                    investment_objective=objective,
                    risk_tolerance=risk,
                    time_horizon="10+ years",
                    investment_experience="Intermediate",
                    liquidity_needs="Keep household reserve available",
                    retirement_age=67,
                    emergency_fund_months=6,
                    tax_filing_status="Married filing jointly"
                    if marital == "Married"
                    else "Single",
                    notes="Fictional household for the hackathon. All records are synthetic.",
                ),
                accounts=own,
                activity=sorted(
                    activity, key=lambda t: (t["date"], t["event_id"]), reverse=True
                ),
                as_of=AS_OF,
                synthetic_only=True,
            )
        )
    return output
