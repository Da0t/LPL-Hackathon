"""Builds the structured case record after client confirmation (Agent 2).

The triage model proposes summaries, categories, unresolved questions, and
flags. Deterministic code owns: account facts (from records with source ids),
contradiction statements, security routing, destination, and advisor ranking.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.schemas import CaseRecord, SECURITY_DESTINATION
from backend.services import routing
from backend.services.agent_adapter import AdapterError, AgentAdapter
from backend.services.case_facts import account_context, wording_conflicts
from backend.services.common import now_iso
from backend.services.mock_agent import INTENT_CATEGORIES, SECURITY_INTENT
from backend.services.text_rules import amount_matches_text, detect_security_concern, mentioned_account_types
from backend.services.tools import build_tools, public_account_view
from backend.services.validation import validate_triage_output
from backend.store import Store

log = logging.getLogger("samepage.triage")


def _input_mode(session: dict[str, Any]) -> str:
    modes = session.get("input_modes") or []
    if len(modes) > 1:
        return "mixed"
    return modes[0] if modes else "text"


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    for item in items:
        if item not in out:
            out.append(item)
    return out


def build_case(
    *,
    store: Store,
    adapter: AgentAdapter,
    session: dict[str, Any],
    confirmed_plain_language_request: str,
    selected_account: dict[str, Any] | None,
    amount_requested: float | int | None,
) -> dict[str, Any]:
    client_id = session["client_id"]
    client = store.get_client(client_id) or {"client_id": client_id, "display_name": session.get("client_display_name", "Client")}
    original_words = session["transcript"]
    owned_accounts = store.accounts_for_client(client_id)
    owned_types = {a.get("account_type") for a in owned_accounts}

    # ---- deterministic facts and flags ------------------------------------
    flags: list[str] = []
    conflicts, mismatch = wording_conflicts(original_words, confirmed_plain_language_request, selected_account, owned_types)
    if mismatch:
        flags.append("client_term_did_not_match_account_type")
    mentioned = mentioned_account_types(f"{original_words} {confirmed_plain_language_request}")
    missing_types = [t for t in mentioned if t not in owned_types]
    security_hits = detect_security_concern(f"{original_words} {confirmed_plain_language_request}")
    if security_hits:
        flags.append("security_keywords_detected")
    if session.get("client_requested_person"):
        flags.append("client_requested_human_help")
    if amount_requested is not None and not amount_matches_text(float(amount_requested), original_words):
        flags.append("amount_not_in_transcript")
    if selected_account is None:
        account_match_status = "unresolved"
    elif selected_account["account_id"] in {session.get("selected_account_id"), session.get("candidate_account_id")} or selected_account["account_id"] in session.get("offered_account_ids", []):
        account_match_status = "client_confirmed"
    else:
        account_match_status = "client_selected"
        flags.append("account_selected_outside_suggestions")

    case_id = store.allocate_case_id()
    now = now_iso()

    # ---- triage model (proposal only) -------------------------------------
    confirmed_request = {
        "case_id": case_id,
        "client_id": client_id,
        "client_display_name": client.get("display_name"),
        "original_words": original_words,
        "confirmed_plain_language_request": confirmed_plain_language_request,
        "input_mode": _input_mode(session),
        "selected_account_id": selected_account["account_id"] if selected_account else None,
        "selected_account": public_account_view(selected_account) if selected_account else None,
        "account_match_status": account_match_status,
        "amount_requested": amount_requested,
        "currency": "USD" if amount_requested is not None else None,
        "candidate_intent": session.get("candidate_intent"),
        "conversation_notes": list(session.get("uncertainties", [])),
        "client_requested_person": bool(session.get("client_requested_person")),
        "authorized_account_types": sorted(t for t in owned_types if t),
        "mentioned_account_types": mentioned,
        "missing_account_types": missing_types,
    }
    tools = build_tools(store, client_id, lambda: {"turns": [], "confirmed_request": confirmed_request}, stage="triage")
    known_advisors = {a["advisor_id"] for a in store.list_advisors()}
    triage_status = "completed"
    triage_error: str | None = None
    try:
        raw = adapter.triage_case(confirmed_request, tools)
        triage = validate_triage_output(raw, known_advisors)
    except AdapterError as exc:
        triage_status = "failed"
        triage_error = exc.code
        log.warning("triage adapter failed for %s: %s", case_id, triage_error)
        fallback_intent = session.get("candidate_intent") or ""
        triage = {
            "client_summary": None,
            "staff_summary": None,
            "intent": session.get("candidate_intent"),
            "categories": list(INTENT_CATEGORIES.get(fallback_intent, ["other_or_unclear"])),
            "unresolved_questions": ["Automated triage was unavailable; staff should classify this request."],
            "flags": ["triage_unavailable"],
            "urgency_level": "none",
            "urgency_reason": None,
            "recommended_destination": None,
            "recommended_advisor_ids": [],
            "notes": [f"triage adapter failed: {triage_error}"],
        }

    categories = list(triage["categories"])
    for flag in triage["flags"]:
        if flag not in flags:
            flags.append(flag)
    security = (
        bool(security_hits)
        or "fraud_or_security" in categories
        or triage.get("intent") == SECURITY_INTENT
        or triage.get("recommended_destination") == SECURITY_DESTINATION
    )
    if security:
        if "fraud_or_security" in categories:
            categories.remove("fraud_or_security")
        categories.insert(0, "fraud_or_security")
        if "possible_unauthorized_access" not in flags:
            flags.append("possible_unauthorized_access")
        if selected_account is None:
            account_match_status = "not_needed"
    if selected_account is None and account_match_status == "unresolved":
        flags.append("account_unresolved")

    urgency = {"level": triage["urgency_level"], "reason": triage["urgency_reason"]}
    if security:
        urgency = {"level": "elevated", "reason": triage["urgency_reason"] or "Possible fraud, unauthorized access, or account takeover indicated by the client's words."}

    # ---- routing (deterministic) -------------------------------------------
    destination, reason = routing.destination_for(categories, security)
    existing_advisor_id = store.existing_advisor_id(client_id)
    candidates = routing.rank_advisors(store.list_advisors(), categories, client, existing_advisor_id, destination)

    staff_summary = triage["staff_summary"] or f"Client request (automated triage unavailable; staff review required): \"{confirmed_plain_language_request}\""
    unresolved = list(triage["unresolved_questions"])
    if selected_account is None and not security and not any("account" in q.lower() for q in unresolved):
        unresolved.insert(0, "Which account the request concerns")
    if amount_requested is None and "withdrawal_or_distribution" in categories and not any("amount" in q.lower() for q in unresolved):
        unresolved.insert(0, "Amount requested (not stated or not confirmed)")

    history = [
        {"event": "client_confirmed", "at": now, "details": {"session_id": session["session_id"]}},
        {"event": "case_created", "at": now, "details": {"status": "submitted"}},
        {"event": "triage_completed" if triage_status == "completed" else "triage_failed", "at": now,
         "details": {"adapter": adapter.name, "error": triage_error, "validation_notes": triage["notes"]}},
    ]
    conversation = [
        {
            "turn_number": t["turn_number"], "text": t["text"], "input_mode": t.get("input_mode", "text"),
            "selected_option_id": t.get("selected_option_id"), "selected_option_label": t.get("selected_option_label"),
            "suggestions": t.get("suggestions", []), "question": t.get("question"), "uncertainty": t.get("uncertainty"),
            "candidate_intent": t.get("candidate_intent"), "candidate_account_id": t.get("candidate_account_id"),
            "degraded": bool(t.get("degraded")), "received_at": t.get("received_at"), "at": t["at"],
        }
        for t in session.get("turns", [])
    ]

    case = {
        "case_id": case_id,
        "client_id": client_id,
        "client_display_name": client.get("display_name") or "Client",
        "created_at": now,
        "status": "submitted",
        "input_mode": _input_mode(session),
        "original_words": original_words,
        "confirmed_plain_language_request": confirmed_plain_language_request,
        "staff_summary": staff_summary,
        "intent": triage["intent"] or session.get("candidate_intent"),
        "amount_requested": amount_requested,
        "currency": "USD" if amount_requested is not None else None,
        "selected_account_id": selected_account["account_id"] if selected_account else None,
        "account_match_status": account_match_status,
        "categories": categories,
        "unresolved_questions": unresolved,
        "flags": _dedupe(flags),
        "account_context": account_context(selected_account, store.events_for_account(selected_account["account_id"]), categories) if selected_account else None,
        "routing": {
            "destination": destination,
            "recommended_advisor_ids": [c["advisor_id"] for c in candidates],
            "assigned_advisor_id": None,
            "staff_decision": None,
            "reason": reason,
            "staff_decision_detail": None,
            "model_recommended_advisor_ids": list(triage["recommended_advisor_ids"]),
            "model_routing_hint": triage.get("recommended_destination"),
        },
        "preferred_contact_channel": client.get("preferred_contact_channel"),
        "client_confirmed_at": now,
        "updated_at": now,
        "conflicts": conflicts,
        "urgency": urgency,
        "existing_advisor_id": existing_advisor_id,
        "conversation": conversation,
        "history": history,
        "triage": {"status": triage_status, "adapter": adapter.name, "error": triage_error, "validation_notes": list(triage["notes"])},
    }
    record = CaseRecord.model_validate(case).model_dump()
    record["_client_summary"] = triage.get("client_summary")  # consumed by intake.confirm, not stored
    return record
