"""Authorized tool callbacks handed to the language-model adapter.

The adapter (Agent 1's Bedrock code or the local mock) never reads storage.
It receives this :class:`ToolBox`, scoped to one client session, and every
callback enforces that scope. Balances and other account facts are **not**
exposed to the model; they are assembled deterministically by the backend from
records with source ids.

Callback shapes (also documented in README.md):

``get_relevant_accounts(client_id, phrase) -> dict``
    ``{"client_id", "accounts": [...], "mentioned_account_types", "missing_account_types",
    "former_employer_mentioned", "error"}``. Each account: ``account_id, account_type,
    label, familiar_label, masked_identifier, ownership, former_employer,
    matched_terms, relevance``. Sorted by relevance, no balances.
``get_approved_definition(term) -> dict | None``
    ``{"term", "plain", "source": "approved_glossary"}``
``get_relevant_account_history(account_id) -> dict``
    ``{"account_id", "account_type", "label", "masked_identifier", "events": [{type, date,
    source_id, description}], "error"}``
``search_advisor_directory(categories, preferences) -> dict``
    ``{"destination", "destination_reason", "candidates": [...]}``
``get_session_context() -> dict``  (extra)
    Prior turns, questions asked, suggestions offered, and selections made.
``list_glossary_terms() -> list[dict]``  (extra)
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable

from backend.services import routing
from backend.services.text_rules import mentioned_account_types, mentions_former_employer
from backend.store import Store, normalize_text

log = logging.getLogger("samepage.tools")

ACCOUNT_TYPE_HINTS: dict[str, list[str]] = {
    "rollover_ira": ["rollover", "rolled over", "old job", "former employer", "previous employer", "old employer", "401k", "401 k", "403b", "403 b", "retirement", "ira", "pension", "from work", "used to work"],
    "roth_ira": ["roth", "retirement", "ira"],
    "traditional_ira": ["traditional", "retirement", "ira"],
    "sep_ira": ["sep", "retirement", "ira", "self employed"],
    "simple_ira": ["simple", "retirement", "ira"],
    "brokerage": ["brokerage", "investment", "investments", "stocks", "stock", "funds", "taxable"],
    "joint_brokerage": ["joint", "brokerage", "investment", "investments", "together", "husband", "wife", "spouse", "stocks"],
    "trust": ["trust"],
    "checking": ["checking", "bank"],
    "savings": ["savings", "bank"],
    "401k": ["401k", "401 k", "work plan", "employer plan", "retirement"],
}


class ToolBox(dict):
    """Dict of callbacks that also supports attribute access (``tools.get_x``)."""

    def __getattr__(self, name: str) -> Callable[..., Any]:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def _match_terms(account: dict[str, Any], phrase_norm: str) -> list[str]:
    haystack = f" {phrase_norm} "
    hints = list(ACCOUNT_TYPE_HINTS.get(account.get("account_type", ""), []))
    for field in ("label", "familiar_label", "former_employer"):
        value = account.get(field)
        if value:
            words = [w for w in normalize_text(str(value)).split() if len(w) > 3 and w not in {"account", "your", "from", "with", "that", "this", "each", "main", "yourself"}]
            hints.extend(words)
            if field == "former_employer":
                hints.append(normalize_text(str(value)))
    matched: list[str] = []
    for hint in hints:
        needle = normalize_text(hint)
        if needle and f" {needle} " in haystack and hint not in matched:
            matched.append(hint)
    return matched


def public_account_view(account: dict[str, Any]) -> dict[str, Any]:
    """Account fields safe to show the model and the client: no balances."""
    return {
        "account_id": account["account_id"],
        "account_type": account.get("account_type"),
        "label": account.get("label"),
        "familiar_label": account.get("familiar_label"),
        "masked_identifier": account.get("masked_identifier"),
        "ownership": account.get("ownership"),
        "former_employer": account.get("former_employer"),
    }


def build_tools(
    store: Store,
    client_id: str,
    session_context: Callable[[], dict[str, Any]] | None = None,
) -> ToolBox:
    """Create the authorized callbacks for one client session."""

    owned_accounts = {a["account_id"]: a for a in store.accounts_for_client(client_id)}
    client = store.get_client(client_id) or {"client_id": client_id}

    def get_relevant_accounts(requested_client_id: str | None = None, phrase: str = "") -> dict[str, Any]:
        if requested_client_id not in (None, "", client_id):
            log.warning("tool get_relevant_accounts refused: session client %s asked for %s", client_id, requested_client_id)
            return {"client_id": client_id, "accounts": [], "mentioned_account_types": [], "missing_account_types": [],
                    "former_employer_mentioned": False, "error": "not_authorized"}
        phrase_norm = normalize_text(phrase or "")
        results = []
        for account in owned_accounts.values():
            view = public_account_view(account)
            view["matched_terms"] = _match_terms(account, phrase_norm)
            view["relevance"] = len(view["matched_terms"])
            results.append(view)
        results.sort(key=lambda a: (-a["relevance"], a["account_id"]))
        mentioned = mentioned_account_types(phrase or "")
        owned_types = {a.get("account_type") for a in owned_accounts.values()}
        return {
            "client_id": client_id,
            "accounts": results,
            "mentioned_account_types": mentioned,
            "missing_account_types": [t for t in mentioned if t not in owned_types],
            "former_employer_mentioned": mentions_former_employer(phrase or ""),
            "error": None,
        }

    def get_approved_definition(term: str) -> dict[str, Any] | None:
        entry = store.glossary_lookup(term or "")
        if not entry:
            return None
        return {"term": entry["term"], "plain": entry["plain"], "source": "approved_glossary"}

    def get_relevant_account_history(account_id: str) -> dict[str, Any]:
        account = owned_accounts.get(account_id)
        if not account:
            log.warning("tool get_relevant_account_history refused for %s (client %s)", account_id, client_id)
            return {"account_id": account_id, "events": [], "error": "not_authorized"}
        events = [
            {"type": e.get("type"), "date": e.get("date"), "source_id": e.get("source_id"), "description": e.get("description")}
            for e in store.events_for_account(account_id)
        ]
        view = public_account_view(account)
        view["events"] = events
        view["error"] = None
        return view

    def search_advisor_directory(categories: list[str] | None = None, preferences: dict[str, Any] | None = None) -> dict[str, Any]:
        categories = [str(c) for c in (categories or [])]
        preferences = preferences or {}
        security = bool(preferences.get("security_concern")) or "fraud_or_security" in categories
        destination, reason = routing.destination_for(categories, security)
        pref_client = dict(client)
        if preferences.get("meeting_preference"):
            pref_client["preferred_contact_channel"] = preferences["meeting_preference"]
        candidates = routing.rank_advisors(
            store.list_advisors(), categories, pref_client, store.existing_advisor_id(client_id), destination
        )
        return {"destination": destination, "destination_reason": reason, "candidates": candidates}

    def get_session_context() -> dict[str, Any]:
        if session_context is None:
            return {"turns": [], "selected_account_id": None, "candidate_account_id": None, "candidate_intent": None,
                    "client_requested_person": False, "offered_account_ids": []}
        return session_context()

    def list_glossary_terms() -> list[dict[str, Any]]:
        return [{"key": g["key"], "term": g["term"]} for g in store.list_glossary()]

    return ToolBox(
        get_relevant_accounts=get_relevant_accounts,
        get_approved_definition=get_approved_definition,
        get_relevant_account_history=get_relevant_account_history,
        search_advisor_directory=search_advisor_directory,
        get_session_context=get_session_context,
        list_glossary_terms=list_glossary_terms,
    )


_ = re  # keep import for potential pattern use by callers
