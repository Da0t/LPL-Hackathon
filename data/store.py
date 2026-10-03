"""Read-only access to the fictional data in data/*.json.

Offered to Agent 2 as a ready data layer; nothing requires using it. `Store` provides
the four authorized callbacks that Agent 1's adapter expects as its `tools` object
(see AWS_SETUP.md, "The seam to Agent 2"), plus the deterministic pieces the staff
endpoints need: verified account context and advisor candidates in the spec's routing
order. It never invents a record: unknown IDs return None or an empty list.

    from data.store import Store
    store = Store()
    intake_turn(client_id, transcript, selected_option_id, tools=store)
"""

from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
NAMES = ("clients", "accounts", "events", "advisors", "glossary", "cases")

# Which earlier events help explain a request in each category.
RELEVANT_EVENT_TYPES = {
    "retirement_income": {"rollover", "transfer", "contribution"},
    "withdrawal_or_distribution": {"rollover", "transfer", "contribution"},
    "rollover_or_transfer": {"rollover", "transfer"},
    "investment_planning": {"contribution", "deposit", "transfer"},
    "beneficiary_or_estate": {"beneficiary_update"},
    "fraud_or_security": {"security_alert"},
    "account_service": {"service_request"},
}
# Words a client may use for an account type, for spotting wording that conflicts with records.
ACCOUNT_TYPE_WORDS = {
    "roth": "roth_ira",
    "rollover": "rollover_ira",
    "traditional ira": "traditional_ira",
    "brokerage": "brokerage",
}


def _plain(value: str) -> str:
    return value.replace("_", " ").replace("ira", "IRA")


class Store:
    def __init__(self, data_dir: Path = DATA_DIR):
        self.data = {name: json.loads((Path(data_dir) / f"{name}.json").read_text())[name] for name in NAMES}
        self._clients = {c["client_id"]: c for c in self.data["clients"]}
        self._accounts = {a["account_id"]: a for a in self.data["accounts"]}
        self._advisors = {a["advisor_id"]: a for a in self.data["advisors"]}

    # ----- lookups -----

    def client(self, client_id: str) -> dict | None:
        return self._clients.get(client_id)

    def account(self, account_id: str) -> dict | None:
        return self._accounts.get(account_id)

    def advisor(self, advisor_id: str) -> dict | None:
        return self._advisors.get(advisor_id)

    def owns(self, client_id: str, account_id: str) -> bool:
        account = self.account(account_id)
        return bool(account) and account["client_id"] == client_id

    # ----- the four callbacks Agent 1's adapter calls -----

    def get_relevant_accounts(self, client_id: str, phrase: str = "") -> list[dict]:
        """Every account the client is authorized to see. Balances are deliberately left out."""
        return [
            {key: a[key] for key in ("account_id", "account_type", "familiar_label", "masked_identifier")}
            for a in self.data["accounts"] if a["client_id"] == client_id
        ]

    def get_approved_definition(self, term: str) -> dict | None:
        wanted = (term or "").strip().lower()
        if not wanted:
            return None
        for entry in self.data["glossary"]:
            names = [entry["term"]] + entry.get("also_heard_as", [])
            if wanted in (name.lower() for name in names):
                return {"term": entry["term"], "plain": entry["plain"]}
        return None

    def get_relevant_account_history(self, account_id: str) -> list[dict]:
        return [
            {key: e[key] for key in ("type", "date", "source_id", "summary")}
            for e in self.data["events"] if e["account_id"] == account_id
        ]

    def search_advisor_directory(self, categories: list[str], preferences: dict | None = None) -> list[dict]:
        """Active, available advisors with a matching specialty; best match first."""
        wanted = set(categories or [])
        mode = (preferences or {}).get("meeting_preference")
        rows = [
            a for a in self.data["advisors"]
            if a["active"] and a["available"] and (not wanted or wanted & set(a["specialties"]))
        ]
        rows.sort(key=lambda a: (-len(wanted & set(a["specialties"])), mode not in a["meeting_mode"], -a["capacity"]))
        return [
            {key: a[key] for key in ("advisor_id", "display_name", "specialties", "available", "meeting_mode", "capacity")}
            for a in rows
        ]

    # ----- deterministic pieces for the staff endpoints -----

    def account_context(self, account_id: str | None, categories: list[str] | None = None,
                        extended: bool = False) -> dict | None:
        """Verified account facts for a case, each with a source ID. None if no such account."""
        account = self.account(account_id) if account_id else None
        if not account:
            return None
        wanted = set()
        for category in categories or []:
            wanted |= RELEVANT_EVENT_TYPES.get(category, set())
        events = [e for e in self.data["events"] if e["account_id"] == account_id]
        relevant = [e for e in events if e["type"] in wanted] if wanted else events
        context = {
            "account_type": account["account_type"],
            "masked_identifier": account["masked_identifier"],
            "balance": account["balance"],
            "balance_as_of": account["balance_as_of"],
            "account_source_id": account["source_id"],
            "relevant_events": [
                {"type": e["type"], "date": e["date"], "source_id": e["source_id"],
                 **({"summary": e["summary"]} if extended else {})}
                for e in sorted(relevant, key=lambda e: e["date"])
            ],
        }
        if extended:
            context["familiar_label"] = account["familiar_label"]
            context["currency"] = account["currency"]
        return context

    def wording_conflicts(self, client_id: str, original_words: str, account_id: str | None) -> list[dict]:
        """Account-type words the client used that their records do not support."""
        account = self.account(account_id) if account_id else None
        if not account:
            return []
        held = {a["account_type"] for a in self.data["accounts"] if a["client_id"] == client_id}
        text = (original_words or "").lower()
        conflicts = []
        for word, account_type in ACCOUNT_TYPE_WORDS.items():
            if word in text and account_type != account["account_type"]:
                absent = "no such account appears in the client's authorized account list" \
                    if account_type not in held else "the client confirmed a different account"
                conflicts.append({
                    "statement": f"Client said \"{word.capitalize()}\"; {absent}. "
                                 f"The confirmed account is recorded as a {_plain(account['account_type'])}.",
                    "source_id": account["source_id"],
                })
        return conflicts

    def rank_candidates(self, client_id: str, categories: list[str], extended: bool = False) -> list[dict]:
        """Up to three candidates: existing advisor first, then availability, specialty
        match, meeting mode, capacity. Empty for fraud or security cases."""
        if "fraud_or_security" in categories:
            return []
        client = self.client(client_id) or {}
        wanted = set(categories)
        ranked = []
        for advisor in self.data["advisors"]:
            if not advisor["active"]:
                continue
            existing = advisor["advisor_id"] == client.get("existing_advisor_id")
            matched = [s for s in advisor["specialties"] if s in wanted]
            if not existing and not matched:
                continue
            meets = client.get("meeting_preference") in advisor["meeting_mode"]
            reasons = []
            if existing:
                reasons.append("Client's current advisor")
            if matched:
                reasons.append("Specialty match: " + ", ".join(_plain(m) for m in matched))
            reasons.append("available for a new case" if advisor["available"] else "not taking new cases")
            if meets:
                reasons.append("offers the client's preferred " + _plain(client["meeting_preference"]) + " meetings")
            candidate = {
                "advisor_id": advisor["advisor_id"],
                "display_name": advisor["display_name"],
                "specialties": advisor["specialties"],
                "available": advisor["available"],
                "reason": "; ".join(reasons) + ".",
            }
            if extended:
                candidate.update(existing_client_relationship=existing,
                                 meeting_mode=advisor["meeting_mode"], capacity=advisor["capacity"])
            order = (not existing, not advisor["available"], -len(matched), not meets, -advisor["capacity"])
            ranked.append((order, candidate))
        return [candidate for _, candidate in sorted(ranked, key=lambda pair: pair[0])[:3]]
