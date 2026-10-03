"""Validators for dictionaries returned by the language-model adapter.

The model is a proposal engine, not a source of account facts. These functions
coerce the adapter output into the shapes the backend expects, drop anything
unsupported (unknown categories, unauthorized account ids, definitions that are
not in the approved glossary, account facts), and return notes describing what
was dropped so staff can see it. They never raise on odd input.
"""

from __future__ import annotations

from typing import Any

import json
from typing import Any as _Any

from backend.schemas import CATEGORY_TAXONOMY, DESTINATIONS, MAX_SUGGESTIONS, RESERVED_OPTION_IDS, SECURITY_DESTINATION
from backend.services.agent_adapter import AdapterError
from backend.services.text_rules import slugify_flag

# Flags the model may assert directly; anything else it returns is kept with a ``model_`` prefix.
MODEL_ALLOWED_FLAGS = {"client_term_did_not_match_account_type", "possible_unauthorized_access"}
# Flags only deterministic backend code may set; a model claiming them is dropped and noted.
BACKEND_OWNED_FLAGS = {
    "security_keywords_detected", "amount_not_in_transcript", "account_unresolved", "account_selected_outside_suggestions",
    "client_requested_human_help", "triage_unavailable", "staff_overrode_recommendation", "staff_overrode_specialist_recommendation",
}


def coerce_adapter_result(raw: _Any, stage: str) -> dict[str, _Any]:
    """Accept a dict, a dict-like object (pydantic/dataclass), or a JSON string; otherwise fail the call
    so the backend takes the preserved-draft path instead of treating garbage as a finished answer."""
    if isinstance(raw, dict):
        return raw
    for attr in ("model_dump", "dict", "to_dict", "_asdict"):
        method = getattr(raw, attr, None)
        if callable(method):
            try:
                value = method()
            except Exception:  # noqa: BLE001
                continue
            if isinstance(value, dict):
                return value
    if isinstance(raw, str):
        try:
            value = json.loads(raw)
        except ValueError:
            value = None
        if isinstance(value, dict):
            return value
    if hasattr(raw, "__dict__") and isinstance(vars(raw), dict) and vars(raw):
        return dict(vars(raw))
    raise AdapterError(f"{stage} adapter returned {type(raw).__name__}, not a dict", code="ADAPTER_BAD_RESULT")

# Destination spellings other components have used, mapped to the canonical names.
_DESTINATION_ALIASES = {
    "specialist_security_review": SECURITY_DESTINATION,
    "security_review": SECURITY_DESTINATION,
    "security_specialist_queue": SECURITY_DESTINATION,
    "estate_planning_advisor_review": "estate_and_beneficiary_review",
    "general_advisor_review": "advisor_review",
    "investment_advisor_review": "advisor_review",
    "client_service_review": "advisor_review",
    "staff_review": "advisor_review",
}


def _clean_str(value: Any, max_len: int = 2000) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    return text[:max_len] if text else None


def _clean_str_list(value: Any, max_items: int = 12, max_len: int = 500, split_commas: bool = False) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [p.strip() for p in value.split(",")] if split_commas and "," in value else [value]
    if not isinstance(value, (list, tuple, set)):
        return []
    out: list[str] = []
    for item in value:
        text = _clean_str(item, max_len)
        if text and text not in out:
            out.append(text)
        if len(out) >= max_items:
            break
    return out


def validate_intake_output(raw: Any, authorized_account_ids: set[str], glossary_lookup) -> dict[str, Any]:
    """Returns keys: suggestions, question, definitions, candidate_intent, candidate_account_id,
    uncertainty, proposed_plain_language_request, notes."""
    notes: list[str] = []
    raw = coerce_adapter_result(raw, "intake")

    suggestions: list[dict[str, Any]] = []
    raw_suggestions = raw.get("suggestions", raw.get("options"))
    if raw_suggestions is None:
        raw_suggestions = []
    if not isinstance(raw_suggestions, list):
        notes.append("suggestions was not a list; ignored")
        raw_suggestions = []
    if len(raw_suggestions) > MAX_SUGGESTIONS:
        notes.append(f"adapter returned {len(raw_suggestions)} suggestions; truncated to {MAX_SUGGESTIONS}")
    seen_ids: set[str] = set()
    for index, item in enumerate(raw_suggestions):
        if isinstance(item, str):
            item = {"label": item}
        if not isinstance(item, dict):
            continue
        label = _clean_str(item.get("label") or item.get("text"), 300)
        if not label:
            continue
        sid = _clean_str(item.get("id") or item.get("option_id"), 64) or f"opt-{index + 1}"
        if sid.lower() in RESERVED_OPTION_IDS:
            notes.append(f"suggestion id '{sid}' is reserved for the client UI; renamed")
            sid = f"opt-{index + 1}"
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

    definitions: list[dict[str, str]] = []
    raw_defs = raw.get("definitions") or []
    if isinstance(raw_defs, dict):
        raw_defs = [{"term": k, "plain": v} for k, v in raw_defs.items()]
    if not isinstance(raw_defs, list):
        raw_defs = []
    for item in raw_defs:
        term = _clean_str(item.get("term"), 100) if isinstance(item, dict) else _clean_str(item, 100)
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

    return {
        "suggestions": suggestions,
        "question": _clean_str(raw.get("question"), 600),
        "definitions": definitions,
        "candidate_intent": _clean_str(raw.get("candidate_intent") or raw.get("intent"), 80),
        "candidate_account_id": candidate_account_id,
        "uncertainty": _clean_str(raw.get("uncertainty"), 600),
        "proposed_plain_language_request": _clean_str(
            raw.get("proposed_plain_language_request") or raw.get("proposed_request") or raw.get("client_summary"), 1200
        ),
        "notes": notes,
    }


def validate_triage_output(raw: Any, known_advisor_ids: set[str]) -> dict[str, Any]:
    """Returns keys: client_summary, staff_summary, intent, categories, unresolved_questions, flags,
    urgency_level, urgency_reason, recommended_destination, recommended_advisor_ids, notes."""
    notes: list[str] = []
    raw = coerce_adapter_result(raw, "triage")

    categories: list[str] = []
    for item in _clean_str_list(raw.get("categories") or raw.get("category_tags"), max_items=12, max_len=80, split_commas=True):
        slug = slugify_flag(item)
        if slug in CATEGORY_TAXONOMY:
            if slug not in categories:
                categories.append(slug)
        else:
            notes.append(f"unknown category '{item}' dropped")
    if not categories:
        categories = ["other_or_unclear"]
        notes.append("no valid categories returned; defaulted to other_or_unclear")

    flags: list[str] = []
    for item in _clean_str_list(raw.get("flags"), max_items=12, max_len=80, split_commas=True):
        slug = slugify_flag(item)
        if not slug:
            continue
        if slug in BACKEND_OWNED_FLAGS:
            notes.append(f"model asserted backend-owned flag '{slug}'; dropped")
            continue
        if slug not in MODEL_ALLOWED_FLAGS and not slug.startswith("model_"):
            slug = f"model_{slug}"[:64]
        if slug not in flags:
            flags.append(slug)

    for forbidden in ("account_context", "balance", "balance_as_of", "relevant_events", "amount_requested", "conflicts"):
        if forbidden in raw and raw[forbidden] not in (None, [], {}, ""):
            notes.append(f"adapter returned '{forbidden}'; ignored because account facts come only from records")

    urgency_raw = raw.get("urgency")
    urgency_level, urgency_reason = "none", None
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

    destination = _clean_str(raw.get("routing_hint") or raw.get("recommended_destination") or raw.get("destination"), 80)
    if destination:
        destination = _DESTINATION_ALIASES.get(slugify_flag(destination), slugify_flag(destination))
        if destination not in DESTINATIONS:
            notes.append(f"unknown destination hint '{destination}' ignored")
            destination = None

    advisor_ids: list[str] = []
    for item in _clean_str_list(raw.get("recommended_advisor_ids"), max_items=5, max_len=32):
        if item in known_advisor_ids:
            advisor_ids.append(item)
        else:
            notes.append(f"recommended advisor '{item}' is not in the directory; ignored")

    return {
        "client_summary": _clean_str(raw.get("client_summary"), 1500),
        "staff_summary": _clean_str(raw.get("staff_summary"), 1500),
        "intent": _clean_str(raw.get("intent") or raw.get("candidate_intent"), 80),
        "categories": categories,
        "unresolved_questions": _clean_str_list(raw.get("unresolved_questions"), max_items=8, max_len=300),
        "flags": flags,
        "urgency_level": urgency_level,
        "urgency_reason": urgency_reason,
        "recommended_destination": destination,
        "recommended_advisor_ids": advisor_ids,
        "notes": notes,
    }
