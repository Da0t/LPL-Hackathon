"""Deterministic routing and advisor ranking (Agent 2).

The language model proposes categories; this module decides the destination
and ranks fictional advisors from the directory. It never invents licensing or
state eligibility: every candidate carries ``eligibility_check`` set to
``manual_verification_required``.
"""

from __future__ import annotations

from typing import Any

from backend.schemas import CATEGORY_TO_DESTINATION, DESTINATIONS

CATEGORY_LABELS: dict[str, str] = {
    "retirement_income": "retirement income",
    "withdrawal_or_distribution": "withdrawals and distributions",
    "rollover_or_transfer": "rollovers and transfers",
    "beneficiary_or_estate": "beneficiary and estate requests",
    "investment_planning": "investment planning",
    "account_service": "account service",
    "fraud_or_security": "fraud and security review",
    "other_or_unclear": "general requests",
}

SPECIALIST_DESTINATION = "specialist_security_review"


def destination_for(categories: list[str], security_concern: bool) -> tuple[str, str]:
    """Return (destination, reason) for a validated category list."""
    if security_concern or "fraud_or_security" in categories:
        return (
            SPECIALIST_DESTINATION,
            "The request indicates possible fraud, unauthorized access, or account takeover. "
            "Routing rule 1: recommend the security specialist review queue instead of a general "
            "planning advisor. Staff makes the final decision.",
        )
    primary = categories[0] if categories else "other_or_unclear"
    destination = CATEGORY_TO_DESTINATION.get(primary, "general_advisor_review")
    reason = (
        f"Primary category '{primary}' maps to {DESTINATIONS[destination].lower()}. "
        "Candidates are ranked by existing relationship, specialty match, availability, "
        "meeting preference, and capacity."
    )
    return destination, reason


def _meeting_preference(client: dict[str, Any] | None) -> str | None:
    if not client:
        return None
    pref = client.get("preferred_contact_channel")
    if not pref:
        return None
    pref = str(pref).strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {"in_person": "in_person", "inperson": "in_person", "office": "in_person", "call": "phone", "telephone": "phone", "zoom": "video", "virtual": "video"}
    return aliases.get(pref, pref)


def _capacity(advisor: dict[str, Any]) -> int:
    value = advisor.get("capacity")
    return int(value) if isinstance(value, (int, float)) else 0


def rank_advisors(
    advisors: list[dict[str, Any]],
    categories: list[str],
    client: dict[str, Any] | None,
    existing_advisor_id: str | None,
    destination: str,
    max_results: int = 3,
) -> list[dict[str, Any]]:
    """Rank the fictional directory for a case. Returns candidate dicts."""
    categories = [c for c in categories if c in CATEGORY_LABELS] or ["other_or_unclear"]
    primary = categories[0]
    preference = _meeting_preference(client)
    specialist = destination == SPECIALIST_DESTINATION

    scored: list[tuple[float, dict[str, Any]]] = []
    for advisor in advisors:
        if not advisor.get("active", True):
            continue
        specialties = [s for s in advisor.get("specialties", [])]
        is_existing = bool(existing_advisor_id) and advisor["advisor_id"] == existing_advisor_id
        matched = [c for c in categories if c in specialties]
        available = bool(advisor.get("available", True))
        capacity = _capacity(advisor)
        modes = list(advisor.get("meeting_modes", []))
        pref_match = bool(preference) and preference in modes

        if specialist:
            # Routing rule 1: only specialist queues/advisors for security concerns.
            if "fraud_or_security" not in specialties:
                continue
            score = 100.0 + (10 if available else 0) + min(capacity, 10)
            reasons = [
                "Specialist review for possible unauthorized access or fraud; not a general planning advisor.",
                "Available now." if available else "Currently at capacity; staff may still choose it.",
                f"Capacity: {capacity}.",
            ]
        else:
            if not matched and not is_existing:
                continue
            score = 0.0
            reasons: list[str] = []
            if is_existing:
                score += 1000  # existing relationship is shown first when active
                reasons.append("Existing advisor for this client.")
            if matched:
                score += 10 * len(matched) + (5 if primary in matched else 0)
                reasons.append("Specialty match: " + ", ".join(CATEGORY_LABELS[c] for c in matched) + ".")
            elif is_existing:
                reasons.append("No direct specialty match for this request; shown because of the existing relationship.")
            if available:
                score += 4
                reasons.append(f"Available ({capacity} open slot{'s' if capacity != 1 else ''}).")
            else:
                reasons.append("Not currently available; staff may still choose this advisor.")
            if pref_match:
                score += 2
                reasons.append(f"Offers {preference.replace('_', ' ')} meetings, matching the client's preference.")
            score += min(capacity, 6) * 0.5
        reasons.append("State and license eligibility must be verified manually; not assessed by the model.")
        scored.append((score, {**advisor, "_reason": " ".join(reasons), "_existing": is_existing}))

    scored.sort(key=lambda item: (-item[0], item[1]["advisor_id"]))
    candidates: list[dict[str, Any]] = []
    for rank, (_, advisor) in enumerate(scored[:max_results], start=1):
        candidates.append(
            {
                "advisor_id": advisor["advisor_id"],
                "display_name": advisor["display_name"],
                "specialties": list(advisor.get("specialties", [])),
                "available": bool(advisor.get("available", True)),
                "reason": advisor["_reason"],
                "rank": rank,
                "existing_relationship": bool(advisor["_existing"]),
                "active": bool(advisor.get("active", True)),
                "meeting_modes": list(advisor.get("meeting_modes", [])),
                "capacity": advisor.get("capacity"),
                "region": advisor.get("region"),
                "kind": str(advisor.get("kind") or "advisor"),
                "eligibility_check": "manual_verification_required",
            }
        )
    return candidates
