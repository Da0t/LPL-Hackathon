"""Authorized tool callbacks handed to the language-model adapter (the seam in AWS_SETUP.md §8).

The adapter (Agent 1's Bedrock code or the local mock) never reads storage. It
receives this :class:`ToolBox`, scoped to one client session, and every callback
enforces that scope. Balances and other account facts are **not** exposed to the
model; the backend assembles them deterministically from records with source ids.

Callback shapes (keyword or positional arguments both work):

``get_relevant_accounts(client_id, phrase) -> list[dict]``
    each ``{account_id, account_type, familiar_label, masked_identifier, label, ownership,
    former_employer, matched_terms, relevance}``, most relevant first. No balances.
    Another client's id yields ``[]``.
``get_approved_definition(term) -> dict | None``   ``{term, plain, source_id?}``
``get_relevant_account_history(account_id) -> list[dict]``
    each ``{type, date, source_id, summary, description}``; ``[]`` unless the account is the client's.
``search_advisor_directory(categories, preferences) -> list[dict]``
    ranked candidates ``{advisor_id, display_name, specialties, available, reason, meeting_mode,
    capacity, existing_client_relationship, ...}``; ``[]`` for security cases without a specialist.
``get_session_context() -> dict``  (extra: prior turns, questions, suggestions, selections)
``list_glossary_terms() -> list[dict]``  (extra)
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable

from backend.services import routing
from backend.store import Store, normalize_text

log = logging.getLogger("samepage.tools")

ACCOUNT_TYPE_HINTS: dict[str, list[str]] = {
    "rollover_ira": ["rollover", "rolled over", "old job", "former employer", "previous employer", "old employer", "last employer", "former job", "401k", "401 k", "403b", "403 b", "retirement", "ira", "pension", "from work", "used to work", "workplace plan"],
    "roth_ira": ["roth", "retirement", "ira"],
    "traditional_ira": ["traditional", "retirement", "ira", "older retirement"],
    "sep_ira": ["sep", "retirement", "ira", "self employed"],
    "simple_ira": ["simple", "retirement", "ira"],
    "brokerage": ["brokerage", "investment", "investments", "stocks", "stock", "funds", "taxable", "everyday"],
    "joint_brokerage": ["joint", "brokerage", "investment", "investments", "together", "husband", "wife", "spouse", "stocks"],
    "cash_management": ["cash", "cash account", "bank", "checking", "debit"],
    "trust": ["trust"],
    "401k": ["401k", "401 k", "work plan", "employer plan", "retirement"],
}
_STOPWORDS = {"account", "your", "from", "with", "that", "this", "each", "main", "yourself", "retirement", "investments", "investment"}


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
            words = [w for w in normalize_text(str(value)).split() if len(w) > 3 and w not in _STOPWORDS]
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
        "familiar_label": account.get("familiar_label"),
        "masked_identifier": account.get("masked_identifier"),
        "label": account.get("label"),
        "ownership": account.get("ownership"),
        "former_employer": account.get("former_employer"),
    }


def build_tools(store: Store, client_id: str, session_context: Callable[[], dict[str, Any]] | None = None, stage: str = "intake") -> ToolBox:
    """Create the authorized callbacks for one client session.

    ``stage="intake"`` exposes only the account list and glossary (the smallest context the
    intake agent needs, per the spec); ``stage="triage"`` adds account history and the advisor
    directory, which are needed only after the client has confirmed.
    """

    owned_accounts = {a["account_id"]: a for a in store.accounts_for_client(client_id)}
    client = store.get_client(client_id) or {"client_id": client_id}
    known_clients = {c["client_id"] for c in store.list_clients()}

    def get_relevant_accounts(client_id_arg: str | None = None, phrase: str = "", **kwargs: Any) -> list[dict[str, Any]]:
        requested = kwargs.get("client_id", client_id_arg)
        # Tolerate a single positional phrase (``tools.get_relevant_accounts("my roth")``).
        if requested not in (None, "", client_id) and not phrase and requested not in known_clients and " " in str(requested):
            phrase, requested = str(requested), client_id
        if requested not in (None, "", client_id):
            log.warning("tool get_relevant_accounts refused: session client %s asked for %s", client_id, requested)
            return []
        phrase_norm = normalize_text(phrase or "")
        results = []
        for account in owned_accounts.values():
            view = public_account_view(account)
            view["matched_terms"] = _match_terms(account, phrase_norm)
            view["relevance"] = len(view["matched_terms"])
            results.append(view)
        results.sort(key=lambda a: (-a["relevance"], a["account_id"]))
        return results

    def get_approved_definition(term: str = "", **kwargs: Any) -> dict[str, Any] | None:
        entry = store.glossary_lookup(kwargs.get("term", term) or "")
        if not entry:
            return None
        out = {"term": entry["term"], "plain": entry["plain"], "source": "approved_glossary"}
        if entry.get("source_id"):
            out["source_id"] = entry["source_id"]
        return out

    def suggest_terms(fragment: str = "", limit: int = 5, **kwargs: Any) -> list[dict[str, Any]]:
        """Grounded term normalization: map shorthand/acronyms/phonetic fragments to
        approved glossary terms (e.g. 'R O I' -> return on investment, 'the tax form'
        -> 1099-R). Candidates come only from the approved glossary; nothing invented.
        """
        frag = normalize_text(kwargs.get("fragment", fragment) or "")
        if not frag:
            return []
        compact = re.sub(r"[^a-z0-9]", "", frag)
        frag_words = set(re.findall(r"[a-z0-9]+", frag))
        scored: list[tuple[int, dict[str, Any]]] = []
        for entry in store.list_glossary():
            term = entry["term"]
            names_l = [normalize_text(n) for n in [term, *entry.get("aliases", [])]]
            initials = "".join(w[0] for w in re.findall(r"[a-z0-9]+", normalize_text(term)))
            score = 0
            if frag in names_l:
                score = 100
            if compact and compact == initials:
                score = max(score, 92)
            for name in names_l:
                name_compact = re.sub(r"[^a-z0-9]", "", name)
                if compact and compact == name_compact:
                    score = max(score, 96)
                elif compact and len(compact) >= 3 and (compact in name_compact or name_compact in compact):
                    score = max(score, 70)
                if frag and (frag in name or name in frag):
                    score = max(score, 66)
                if frag_words & set(re.findall(r"[a-z0-9]+", name)):
                    score = max(score, 42)
            if frag in normalize_text(term) or normalize_text(term) in frag:
                score = max(score, 62)
            if score:
                out = {"term": term, "plain": entry["plain"]}
                if entry.get("source_id"):
                    out["source_id"] = entry["source_id"]
                scored.append((score, out))
        scored.sort(key=lambda pair: -pair[0])
        return [candidate for _, candidate in scored[:limit]]

    def get_relevant_account_history(account_id: str = "", **kwargs: Any) -> list[dict[str, Any]]:
        account_id = kwargs.get("account_id", account_id)
        if account_id not in owned_accounts:
            log.warning("tool get_relevant_account_history refused for %s (client %s)", account_id, client_id)
            return []
        return [
            {"type": e.get("type"), "date": e.get("date"), "source_id": e.get("source_id"), "summary": e.get("summary"), "description": e.get("description")}
            for e in store.events_for_account(account_id)
        ]

    def search_advisor_directory(categories: list[str] | None = None, preferences: dict[str, Any] | None = None, **kwargs: Any) -> list[dict[str, Any]]:
        categories = [str(c) for c in (kwargs.get("categories", categories) or [])]
        preferences = kwargs.get("preferences", preferences) or {}
        security = bool(preferences.get("security_concern")) or "fraud_or_security" in categories
        destination, _ = routing.destination_for(categories, security)
        pref_client = dict(client)
        if preferences.get("meeting_preference"):
            pref_client["meeting_preference"] = preferences["meeting_preference"]
        return routing.rank_advisors(store.list_advisors(), categories, pref_client, store.existing_advisor_id(client_id), destination)

    def get_session_context() -> dict[str, Any]:
        if session_context is None:
            return {"turns": [], "selected_account_id": None, "candidate_account_id": None, "candidate_intent": None,
                    "client_requested_person": False, "offered_account_ids": [], "last_selected_option": None}
        return session_context()

    def list_glossary_terms() -> list[dict[str, Any]]:
        return [{"key": g["key"], "term": g["term"]} for g in store.list_glossary()]

    tools = ToolBox(
        get_relevant_accounts=get_relevant_accounts,
        get_approved_definition=get_approved_definition,
        suggest_terms=suggest_terms,
        get_session_context=get_session_context,
        list_glossary_terms=list_glossary_terms,
    )
    if stage == "triage":
        tools["get_relevant_account_history"] = get_relevant_account_history
        tools["search_advisor_directory"] = search_advisor_directory
    return tools
