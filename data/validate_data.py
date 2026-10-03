"""Check that data/*.json is coherent and still contains the frozen fixture.

Run from the repository root:

    python3 data/validate_data.py            # check the data
    python3 data/validate_data.py --export   # print one fixture-shaped JSON document
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

DATA = Path(__file__).parent
FIXTURE = json.loads((DATA.parent / "contracts" / "demo_fixture_v1.json").read_text())
CATEGORIES = {
    "retirement_income", "withdrawal_or_distribution", "rollover_or_transfer",
    "beneficiary_or_estate", "investment_planning", "account_service",
    "fraud_or_security", "other_or_unclear",
}
STATUSES = {
    "draft", "needs_clarification", "ready_for_client_review", "submitted",
    "staff_review", "needs_client_followup", "assigned",
}
KEYS = {
    "clients": "client_id", "accounts": "account_id", "events": "source_id",
    "advisors": "advisor_id", "glossary": "term", "cases": "case_id",
}
GLOSSARY_TERMS = {
    "roth ira", "rollover ira", "brokerage account", "beneficiary", "transfer", "withdrawal",
    "distribution", "required minimum distribution", "advisor", "trusted contact",
}
REQUIRED = {
    "accounts": ("client_id", "account_type", "familiar_label", "masked_identifier",
                 "balance", "balance_as_of", "source_id"),
    "events": ("account_id", "type", "date", "source_id"),
    "advisors": ("specialties", "active", "available", "meeting_mode", "capacity"),
    "glossary": ("term", "plain"),
}


def load() -> dict:
    return {name: json.loads((DATA / f"{name}.json").read_text())[name] for name in KEYS}


def check(data: dict) -> list[str]:
    errors = []
    index = {}
    for name, key in KEYS.items():
        ids = [row[key] for row in data[name]]
        if len(ids) != len(set(ids)):
            errors.append(f"{name}: duplicate {key}")
        index[name] = {row[key]: row for row in data[name]}
        for row in data[name]:
            for field in REQUIRED.get(name, ()):
                if field not in row:
                    errors.append(f"{name} {row[key]}: missing {field}")

    # The frozen fixture must survive unchanged inside the expanded data.
    for name, key in KEYS.items():
        for row in FIXTURE[name]:
            ours = index[name].get(row[key])
            if ours is None:
                errors.append(f"{name}: fixture record {row[key]} is missing")
                continue
            for field, value in row.items():
                if ours.get(field) != value:
                    errors.append(f"{name} {row[key]}: {field} differs from the frozen fixture")

    for account in data["accounts"]:
        if account["client_id"] not in index["clients"]:
            errors.append(f"account {account['account_id']}: unknown client")
    for event in data["events"]:
        account = index["accounts"].get(event["account_id"])
        if not account:
            errors.append(f"event {event['source_id']}: unknown account")
        elif event.get("client_id") not in (None, account["client_id"]):
            errors.append(f"event {event['source_id']}: client does not own the account")
    for client in data["clients"]:
        advisor = client["existing_advisor_id"]
        if advisor and advisor not in index["advisors"]:
            errors.append(f"client {client['client_id']}: unknown existing advisor")
    for advisor in data["advisors"]:
        if set(advisor["specialties"]) - CATEGORIES:
            errors.append(f"advisor {advisor['advisor_id']}: unknown specialty")
    sources = {a["source_id"] for a in data["accounts"]} | set(index["events"])
    for case in data["cases"]:
        cid = case["case_id"]
        if case["client_id"] not in index["clients"]:
            errors.append(f"case {cid}: unknown client")
        if case["status"] not in STATUSES:
            errors.append(f"case {cid}: unknown status")
        if set(case["categories"]) - CATEGORIES:
            errors.append(f"case {cid}: unknown category")
        account = index["accounts"].get(case["selected_account_id"])
        if case["selected_account_id"] and (not account or account["client_id"] != case["client_id"]):
            errors.append(f"case {cid}: selected account is not the client's")
        context = case["account_context"]
        if context:
            cited = [context["account_source_id"]] + [e["source_id"] for e in context["relevant_events"]]
            for source in cited:
                if source not in sources:
                    errors.append(f"case {cid}: source {source} does not exist")
        for advisor in case["routing"]["recommended_advisor_ids"]:
            if advisor not in index["advisors"]:
                errors.append(f"case {cid}: unknown recommended advisor {advisor}")

    for name, low, high in (("clients", 3, 3), ("accounts", 6, 8), ("advisors", 8, 8), ("glossary", 10, 10)):
        if not low <= len(data[name]) <= high:
            errors.append(f"{name}: expected {low} to {high} rows, found {len(data[name])}")
    for account in data["accounts"]:
        if not re.fullmatch(r"\*{4}\d{4}", account["masked_identifier"]):
            errors.append(f"account {account['account_id']}: identifier is not masked")
    days = [(a["account_id"], a["balance_as_of"]) for a in data["accounts"]]
    days += [(e["source_id"], e["date"]) for e in data["events"]]
    for owner, day in days:
        try:
            date.fromisoformat(day)
        except ValueError:
            errors.append(f"{owner}: {day} is not a YYYY-MM-DD date")
    terms = {entry["term"].lower() for entry in data["glossary"]}
    missing = GLOSSARY_TERMS - terms
    if missing:
        errors.append("glossary: missing " + ", ".join(sorted(missing)))
    for advisor in data["advisors"]:
        if advisor["available"] and (not advisor["active"] or advisor["capacity"] < 1):
            errors.append(f"advisor {advisor['advisor_id']}: available but inactive or at capacity")
    held = {a["account_type"] for a in data["accounts"]}
    if "roth_ira" not in held:
        errors.append("no client holds a Roth IRA for the clear Roth question")
    if not any(e["type"] == "beneficiary_update" for e in data["events"]):
        errors.append("no beneficiary event for the beneficiary request")
    if not any("fraud_or_security" in c["categories"] and not c["routing"]["recommended_advisor_ids"]
               for c in data["cases"]):
        errors.append("no security case routed to a specialist queue without advisors")

    # The demo depends on this: CLIENT-017 has a rollover IRA and no Roth IRA.
    mara = {a["account_type"] for a in data["accounts"] if a["client_id"] == "CLIENT-017"}
    if "rollover_ira" not in mara or "roth_ira" in mara:
        errors.append("CLIENT-017 must hold a rollover IRA and no Roth IRA")
    return errors


if __name__ == "__main__":
    data = load()
    if "--export" in sys.argv:
        merged = {"meta": {**FIXTURE["meta"], "description": "Merged from data/*.json"}, **data}
        print(json.dumps(merged, indent=2))
        sys.exit(0)
    problems = check(data)
    for problem in problems:
        print("FAIL", problem)
    if problems:
        sys.exit(1)
    print("OK", ", ".join(f"{len(data[name])} {name}" for name in KEYS))
