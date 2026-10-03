"""Validators for dictionaries returned by the language-model adapter.

The model is a proposal engine, not a source of account facts. These
functions coerce the adapter output into the shapes the backend expects, drop
anything unsupported (unknown categories, unauthorized account ids, definitions
that are not in the approved glossary), and return human-readable notes
describing what was dropped so staff can see it.
"""

from __future__ import annotations

from typing import Any

from backend.schemas import CATEGORY_TAXONOMY, DESTINATIONS, MAX_SUGGESTIONS
from backend.services.text_rules import slugify_flag


def _clean_str(value: Any, max_len: int = 2000) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:max_len]


def _clean_str_list(value: Any, max_items: int = 12, max_len: int = 500) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for item in value:
        text = _clean_str(item, max_len)
        if text and text not in out:
            out.append(text)
        if len(out) >= max_items:
            break
    return out


class ValidatedIntake(dict):
    """Dict with keys: suggestions, question, definitions, candidate_intent,
    candidate_account_id, uncertainty, proposed_plain_language_request, notes."""


def validate_intake_output(
    raw: Any,
    authorized_account_ids: set[str],
    glossary_lookup,
) -> ValidatedIntake:
    notes: list[str] = []
    if not isinstance(raw, dict):
        notes.append("adapter returned a non-dict response; treated as empty")
        raw = {}

    # Suggestions: at most three, ids/labels required, account ids must be authorized.
    suggestions: list[dict[str, Any]] = []
    raw_suggestions = raw.get("suggestions")
    if raw_suggestions is None:
        raw_suggestions = []
    if not isinstance(raw_suggestions, list):
        notes.append("suggestions was not a list; ignored")
        raw_suggestions = []
    if len(raw_suggestions) > MAX_SUGGESTIONS:
        notes.append(f"adapter returned {len(raw_suggestions)} suggestions; truncated to {MAX_SUGGESTIONS}")
    seen_ids: set[str] = set()
    for index, item in enumerate(raw_suggestions):
        if not isinstance(item, dict):
            continue
        label = _clean_str(item.get("label") or item.get("text"), 300)
        if not label:
            continue
        sid = _clean_str(item.get("id") or item.get("option_id"), 64) or f"opt-{index + 1}"
        if sid in seen_ids:
            sid = f"{sid}-{index + 1}"
        seen_ids.add(sid)
        account_id = _clean_str(item.get("account_id"), 64)
        if account_id and account_id not in authorized_account_ids:
            notes.append(f"suggestion '{sid}' referenced unauthorized account {account_id}; account reference removed")
            account_id = None
        suggestions.append({"id": sid, "label": label, "account_id": account_id})
        if len(suggestions) >= MAX_SUGGESTIONS:
            break

    # Definitions: only approved glossary text.
    definitions: list[dict[str, str]] = []
    raw_defs = raw.get("definitions") or []
    if isinstance(raw_defs, dict):
        raw_defs = [{"term": k, "plain": v} for k, v in raw_defs.items()]
    if not isinstance(raw_defs, list):
        raw_defs = []
    for item in raw_defs:
        term = None
        if isinstance(item, dict):
            term = _clean_str(item.get("term"), 100)
        elif isinstance(item, str):
            term = _clean_str(item, 100)
        if not term:
            continue
        entry = glossary_lookup(term)
        if not entry:
            notes.append(f"definition for '{term}' is not in the approved glossary; dropped")
            continue
        if any(d["term"] == entry["term"] for d in definitions):
            continue
        definitions.append({"term": entry["term"], "plain": entry["plain"]})
        if len(definitions) >= 4:
            break

    candidate_account_id = _clean_str(raw.get("selected_account_id") or raw.get("candidate_account_id"), 64)
    if candidate_account_id and candidate_account_id not in authorized_account_ids:
        notes.append(f"adapter proposed unauthorized account {candidate_account_id}; ignored")
        candidate_account_id = None

    return ValidatedIntake(
        suggestions=suggestions,
        question=_clean_str(raw.get("question"), 600),
        definitions=definitions,
        candidate_intent=_clean_str(raw.get("candidate_intent") or raw.get("intent"), 80),
        candidate_account_id=candidate_account_id,
        uncertainty=_clean_str(raw.get("uncertainty"), 600),
        proposed_plain_language_request=_clean_str(
            raw.get("proposed_plain_language_request") or raw.get("proposed_request") or raw.get("client_summary"), 1200
        ),
        notes=notes,
    )


class ValidatedTriage(dict):
    """Dict with keys: client_summary, staff_summary, intent, categories,
    unresolved_questions, flags, urgency_level, urgency_reason,
    recommended_destination, recommended_advisor_ids, notes."""


def validate_triage_output(raw: Any, known_advisor_ids: set[str]) -> ValidatedTriage:
    notes: list[str] = []
    if not isinstance(raw, dict):
        notes.append("adapter returned a non-dict response; treated as empty")
        raw = {}

    categories: list[str] = []
    raw_categories = raw.get("categories") or raw.get("category_tags") or []
    if isinstance(raw_categories, str):
        raw_categories = [raw_categories]
    if not isinstance(raw_categories, list):
        raw_categories = []
    for item in raw_categories:
        slug = slugify_flag(str(item))
        if slug in CATEGORY_TAXONOMY:
            if slug not in categories:
                categories.append(slug)
        else:
            notes.append(f"unknown category '{item}' dropped")
    if not categories:
        categories = ["other_or_unclear"]
        notes.append("no valid categories returned; defaulted to other_or_unclear")

    flags = []
    for item in _clean_str_list(raw.get("flags"), max_items=12, max_len=80):
        slug = slugify_flag(item)
        if slug and slug not in flags:
            flags.append(slug)

    # Account facts from the model are never trusted.
    for forbidden in ("account_context", "balance", "balance_as_of", "relevant_events", "amount_requested"):
        if forbidden in raw and raw[forbidden] not in (None, [], {}, ""):
            notes.append(f"adapter returned '{forbidden}'; ignored because account facts come only from records")

    urgency_raw = raw.get("urgency")
    urgency_level = "none"
    urgency_reason = None
    if isinstance(urgency_raw, dict):
        level = str(urgency_raw.get("level") or "none").lower()
        urgency_level = "elevated" if level in {"elevated", "high", "urgent"} else "none"
        urgency_reason = _clean_str(urgency_raw.get("reason"), 300)
    elif isinstance(urgency_raw, str):
        urgency_level = "elevated" if urgency_raw.lower() in {"elevated", "high", "urgent"} else "none"
    elif isinstance(urgency_raw, bool):
        urgency_level = "elevated" if urgency_raw else "none"
    if urgency_level == "elevated" and not urgency_reason:
        urgency_reason = _clean_str(raw.get("urgency_reason"), 300) or "Model marked this request as elevated urgency."

    destination = _clean_str(raw.get("recommended_destination") or raw.get("destination"), 80)
    if destination and destination not in DESTINATIONS:
        notes.append(f"unknown destination '{destination}' ignored")
        destination = None

    advisor_ids: list[str] = []
    for item in _clean_str_list(raw.get("recommended_advisor_ids"), max_items=5, max_len=32):
        if item in known_advisor_ids:
            advisor_ids.append(item)
        else:
            notes.append(f"recommended advisor '{item}' is not in the directory; ignored")

    return ValidatedTriage(
        client_summary=_clean_str(raw.get("client_summary") or raw.get("confirmed_plain_language_request"), 1500),
        staff_summary=_clean_str(raw.get("staff_summary"), 1500),
        intent=_clean_str(raw.get("intent") or raw.get("candidate_intent"), 80),
        categories=categories,
        unresolved_questions=_clean_str_list(raw.get("unresolved_questions"), max_items=8, max_len=300),
        flags=flags,
        urgency_level=urgency_level,
        urgency_reason=urgency_reason,
        recommended_destination=destination,
        recommended_advisor_ids=advisor_ids,
        notes=notes,
    )
