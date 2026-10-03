"""Record-backed case facts shared by live triage and seeded cases (Agent 2).

Everything here is deterministic and sourced: account snapshots, relevant
prior events, wording conflicts, and the normalization of Agent 4's optional
``data/cases.json`` seed cases into the full case record shape.
"""

from __future__ import annotations

from typing import Any

from backend.schemas import CaseRecord, SECURITY_DESTINATION
from backend.services.routing import destination_for
from backend.services.text_rules import account_type_label, mentioned_account_types

STANDARD_CAUTIONS: tuple[str, ...] = (
    "Tax effects and eligibility have not been assessed.",
    "The balance is a snapshot for staff context, not an amount available to withdraw, and not a recommendation.",
)

# Which earlier events help explain a request in each category (shared with Agent 4's data layer).
RELEVANT_EVENT_TYPES: dict[str, set[str]] = {
    "retirement_income": {"rollover", "transfer", "contribution"},
    "withdrawal_or_distribution": {"rollover", "transfer", "contribution"},
    "rollover_or_transfer": {"rollover", "transfer", "account_opened"},
    "investment_planning": {"contribution", "deposit", "transfer"},
    "beneficiary_or_estate": {"beneficiary_update", "account_opened"},
    "fraud_or_security": {"security_alert", "login_alert", "outgoing_transfer", "transfer", "withdrawal"},
    "account_service": {"service_request"},
    "other_or_unclear": set(),
}


def relevant_events(events: list[dict[str, Any]], categories: list[str]) -> list[dict[str, Any]]:
    """Events whose type helps explain the case; all events when no category narrows them."""
    wanted: set[str] = set()
    for category in categories or []:
        wanted |= RELEVANT_EVENT_TYPES.get(category, set())
    chosen = [e for e in events if (e.get("type") in wanted)] if wanted else list(events)
    chosen.sort(key=lambda e: e.get("date") or "")
    out = []
    for event in chosen:
        text = event.get("summary") or event.get("description")
        out.append(
            {
                "type": event.get("type") or "event",
                "date": event.get("date") or "",
                "source_id": event.get("source_id") or event.get("event_id") or "",
                "summary": text,
                "description": text,
            }
        )
    return out


def account_context(account: dict[str, Any], events: list[dict[str, Any]], categories: list[str]) -> dict[str, Any]:
    chosen = relevant_events(events, categories)
    source_id = account.get("source_id")
    sources = [source_id] if source_id else []
    for event in chosen:
        if event["source_id"] and event["source_id"] not in sources:
            sources.append(event["source_id"])
    return {
        "account_type": account.get("account_type") or "unknown",
        "masked_identifier": account.get("masked_identifier") or "****",
        "balance": account.get("balance"),
        "balance_as_of": account.get("balance_as_of"),
        "account_source_id": source_id,
        "relevant_events": chosen,
        "account_id": account.get("account_id"),
        "familiar_label": account.get("familiar_label"),
        "account_label": account.get("label") or account_type_label(account.get("account_type")),
        "currency": account.get("currency") or "USD",
        "ownership": account.get("ownership"),
        "source_id": source_id,
        "cautions": list(STANDARD_CAUTIONS),
        "sources": sources,
    }


def wording_conflicts(
    original_words: str,
    confirmed_wording: str,
    account: dict[str, Any] | None,
    owned_types: set[str],
) -> tuple[list[dict[str, Any]], bool]:
    """Sourced statements where the client's account-type words disagree with the records.

    Returns (conflicts, mismatch_flag). The flag is true when the client named an
    account type they do not hold, or a type different from the confirmed account.
    """
    conflicts: list[dict[str, Any]] = []
    mismatch = False
    said_original = mentioned_account_types(original_words)
    said_any = mentioned_account_types(f"{original_words} {confirmed_wording}")
    source = account.get("source_id") if account else None
    for account_type in said_any:
        if account_type not in owned_types:
            mismatch = True
            label = account_type_label(account_type)
            statement = f"Client said '{label}'; no {label} appears in the authorized account list."
            if account:
                statement += f" The confirmed account is recorded as a {account_type_label(account.get('account_type'))} ({account.get('masked_identifier')})."
            conflicts.append({"statement": statement, "source_id": source})
    if account and said_original and account.get("account_type") not in said_original:
        if account.get("account_type") in owned_types and all(t in owned_types for t in said_original):
            mismatch = True
            said = account_type_label(said_original[0])
            conflicts.append(
                {
                    "statement": f"Client said '{said}'; the confirmed account is recorded as a {account_type_label(account.get('account_type'))} ({account.get('masked_identifier')}).",
                    "source_id": source,
                }
            )
    return conflicts, mismatch


def normalize_seed_case(
    raw: dict[str, Any],
    accounts: dict[str, dict[str, Any]],
    clients: dict[str, dict[str, Any]],
    events_by_account: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Shape one of Agent 4's optional seed cases into the full case record."""
    client = clients.get(str(raw.get("client_id")), {})
    created = str(raw.get("created_at") or "2026-10-02T00:00:00Z")
    categories = [str(c) for c in (raw.get("categories") or ["other_or_unclear"])]
    security = "fraud_or_security" in categories
    amount = raw.get("amount_requested")
    selected_account_id = raw.get("selected_account_id")
    account = accounts.get(str(selected_account_id)) if selected_account_id else None
    owned_types = {a.get("account_type") for a in accounts.values() if a.get("client_id") == raw.get("client_id")}

    context = None
    if account:
        context = account_context(account, events_by_account.get(account["account_id"], []), categories)
    elif isinstance(raw.get("account_context"), dict):
        rc = raw["account_context"]
        context = {
            "account_type": rc.get("account_type") or "unknown",
            "masked_identifier": rc.get("masked_identifier") or "****",
            "balance": rc.get("balance"),
            "balance_as_of": rc.get("balance_as_of"),
            "account_source_id": rc.get("account_source_id") or rc.get("source_id"),
            "relevant_events": [
                {"type": e.get("type", "event"), "date": e.get("date", ""), "source_id": e.get("source_id", ""), "summary": e.get("summary"), "description": e.get("summary")}
                for e in rc.get("relevant_events", []) if isinstance(e, dict)
            ],
            "account_id": selected_account_id,
            "source_id": rc.get("account_source_id") or rc.get("source_id"),
            "currency": rc.get("currency") or "USD",
            "cautions": list(STANDARD_CAUTIONS),
            "sources": [s for s in [rc.get("account_source_id")] if s],
        }

    conflicts, _ = wording_conflicts(str(raw.get("original_words") or ""), str(raw.get("confirmed_plain_language_request") or ""), account, owned_types)
    routing_raw = dict(raw.get("routing") or {})
    destination = str(routing_raw.get("destination") or destination_for(categories, security)[0])
    if security:
        destination = SECURITY_DESTINATION
    reason = routing_raw.get("reason") or destination_for(categories, security)[1]
    staff_decision = routing_raw.get("staff_decision")
    if isinstance(staff_decision, dict):
        staff_decision = staff_decision.get("staff_reason") or None

    flags = [str(f) for f in (raw.get("flags") or [])]
    if security and "possible_unauthorized_access" not in flags:
        flags.append("possible_unauthorized_access")
    match_status = raw.get("account_match_status") or ("not_needed" if security and not account else ("client_confirmed" if account else "unresolved"))

    case = {
        "case_id": str(raw["case_id"]),
        "client_id": str(raw.get("client_id")),
        "client_display_name": raw.get("client_display_name") or client.get("display_name") or "Client",
        "created_at": created,
        "status": str(raw.get("status") or "submitted"),
        "input_mode": str(raw.get("input_mode") or "text"),
        "original_words": str(raw.get("original_words") or ""),
        "confirmed_plain_language_request": str(raw.get("confirmed_plain_language_request") or ""),
        "staff_summary": str(raw.get("staff_summary") or ""),
        "intent": raw.get("intent"),
        "amount_requested": amount,
        "currency": raw.get("currency") if amount is not None else None,
        "selected_account_id": selected_account_id,
        "account_match_status": str(match_status),
        "categories": categories,
        "unresolved_questions": [str(q) for q in (raw.get("unresolved_questions") or [])],
        "flags": flags,
        "account_context": context,
        "routing": {
            "destination": destination,
            "recommended_advisor_ids": [str(a) for a in (routing_raw.get("recommended_advisor_ids") or [])],
            "assigned_advisor_id": routing_raw.get("assigned_advisor_id"),
            "staff_decision": staff_decision,
            "reason": reason,
            "staff_decision_detail": None,
            "model_recommended_advisor_ids": [],
            "model_routing_hint": None,
        },
        "preferred_contact_channel": raw.get("preferred_contact_channel") or client.get("preferred_contact_channel"),
        "client_confirmed_at": raw.get("client_confirmed_at") or created,
        "updated_at": created,
        "conflicts": conflicts,
        "urgency": {"level": "elevated", "reason": "Possible unauthorized access reported by the client."} if security else {"level": "none", "reason": None},
        "existing_advisor_id": client.get("existing_advisor_id"),
        "conversation": [],
        "history": [{"event": "seeded", "at": created, "details": {"source": "seed cases (data/cases.json)"}}],
        "triage": {"status": "seeded", "adapter": "seed", "error": None, "validation_notes": []},
    }
    if amount is not None and case["currency"] is None:
        case["currency"] = "USD"
    return CaseRecord.model_validate(case).model_dump()
