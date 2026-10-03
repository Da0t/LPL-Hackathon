"""Fixture-backed fake tool callbacks for Agent 1 development.

These mimic the authorized ``tools`` object Agent 2 will supply in the real app,
but read only from ``contracts/demo_fixture_v1.json`` (synthetic data). The
production adapter must NOT read files directly; this lives under tests/ on
purpose so Agent 1 can develop and test without the backend.
"""

from __future__ import annotations

import json
from pathlib import Path

_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "contracts" / "demo_fixture_v1.json"
FIXTURE = json.loads(_FIXTURE_PATH.read_text())


class FixtureTools:
    """Implements the four callbacks the Bedrock adapter expects."""

    def get_relevant_accounts(self, client_id: str, phrase: str) -> list[dict]:
        return [
            {
                "account_id": a["account_id"],
                "account_type": a["account_type"],
                "familiar_label": a["familiar_label"],
                "masked_identifier": a["masked_identifier"],
            }
            for a in FIXTURE["accounts"]
            if a["client_id"] == client_id
        ]

    def get_approved_definition(self, term: str) -> dict | None:
        term_l = (term or "").strip().lower()
        for g in FIXTURE["glossary"]:
            if g["term"].lower() == term_l:
                return {"term": g["term"], "plain": g["plain"]}
        return None

    def get_relevant_account_history(self, account_id: str) -> list[dict]:
        return [
            {"type": e["type"], "date": e["date"], "source_id": e["source_id"],
             "summary": e.get("summary")}
            for e in FIXTURE["events"]
            if e["account_id"] == account_id
        ]

    def search_advisor_directory(self, categories: list[str], preferences: dict) -> list[dict]:
        cats = set(categories or [])
        out = []
        for adv in FIXTURE["advisors"]:
            if not adv.get("active", True) or not adv.get("available", True):
                continue
            if cats and not cats.intersection(adv.get("specialties", [])):
                continue
            out.append({
                "advisor_id": adv["advisor_id"],
                "display_name": adv["display_name"],
                "specialties": adv["specialties"],
                "available": adv["available"],
            })
        return out
