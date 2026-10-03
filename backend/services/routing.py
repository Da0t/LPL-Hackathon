"""Deterministic routing and advisor ranking (Agent 2).

The language model proposes categories; this module decides the destination
and ranks fictional advisors from the directory in the product spec's order:

1. Possible fraud, unauthorized access, or account takeover -> the security
   specialist review queue, never a general planning advisor.
2. The client's existing advisor first, when active.
3. Then availability, specialty match, meeting preference, and capacity.
4. At most three candidates, each with a reason.

License and state eligibility are never inferred; every candidate carries
``eligibility_check: manual_verification_required``.
"""

from __future__ import annotations

from typing import Any

from backend.schemas import CATEGORY_TO_DESTINATION, DESTINATIONS, SECURITY_DESTINATION

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

SPECIALIST_DESTINATION = SECURITY_DESTINATION


def destination_for(categories: list[str], security_concern: bool) -> tuple[str, str]:
    """Return (destination, reason) for a validated category list."""
    if security_concern or "fraud_or_security" in categories:
        return (
            SECURITY_DESTINATION,
            "The request indicates possible fraud, unauthorized access, or account takeover. "
            "Routing rule 1 sends it to the security specialist review queue instead of a general "
            "planning advisor. Staff make the final decision.",
        )
    primary = categories[0] if categories else "other_or_unclear"
    destination = CATEGORY_TO_DESTINATION.get(primary, "advisor_review")
    reason = (
        f"Primary category '{primary}' maps to {DESTINATIONS[destination].lower()}. "
        "Candidates are ranked by existing relationship, availability, specialty match, "
        "meeting preference, and capacity."
    )
    return destination, reason


def meeting_preference(client: dict[str, Any] | None) -> str | None:
    """The client's preferred meeting mode, falling back to the contact channel."""
    if not client:
        return None
    pref = client.get("meeting_preference") or client.get("preferred_contact_channel")
    if not pref:
        return None
    pref = str(pref).strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {"inperson": "in_person", "office": "in_person", "call": "phone", "telephone": "phone", "zoom": "video", "virtual": "video"}
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
    preference = meeting_preference(client)
    specialist = destination == SECURITY_DESTINATION

    scored: list[tuple[float, dict[str, Any]]] = []
    for advisor in advisors:
        if not advisor.get("active", True):
            continue  # inactive advisors are never candidates
        specialties = list(advisor.get("specialties", []))
        is_existing = bool(existing_advisor_id) and advisor["advisor_id"] == existing_advisor_id
        matched = [c for c in categories if c in specialties]
        available = bool(advisor.get("available", True))
        capacity = _capacity(advisor)
        modes = list(advisor.get("meeting_mode", []))
        pref_match = bool(preference) and preference in modes
        reasons: list[str] = []

        if specialist:
            # Rule 1: only a security specialist (if the directory has one) may appear.
            if "fraud_or_security" not in specialties:
                continue
            score = 100.0 + (10 if available else 0) + min(capacity, 10)
            reasons.append("Security specialist for possible unauthorized access or fraud; not a general planning advisor.")
            reasons.append("Available now." if available else "Currently at capacity; staff may still choose this queue.")
        else:
            if not matched and not is_existing:
                continue
            score = 0.0
            if is_existing:
                score += 1000
                reasons.append("Client's current advisor.")
            if available:
                score += 100
            score += 10 * len(matched) + (5 if primary in matched else 0)
            if matched:
                reasons.append("Specialty match: " + ", ".join(CATEGORY_LABELS[c] for c in matched) + ".")
            elif is_existing:
                reasons.append("No direct specialty match; shown because of the existing relationship.")
            reasons.append(
                f"Available for a new case ({capacity} open slot{'s' if capacity != 1 else ''})." if available
                else "Not taking new cases right now; staff may still choose this advisor."
            )
            if pref_match:
                score += 2
                reasons.append(f"Offers the client's preferred {preference.replace('_', ' ')} meetings.")
            score += min(capacity, 6) * 0.5
        reasons.append("State and license eligibility must be verified manually; not assessed by the model.")
        scored.append((score, {**advisor, "_reason": " ".join(reasons), "_existing": is_existing}))

    if not scored and not specialist:
        # Unclear/general request with no specialty match and no existing advisor: offer the best
        # available active advisors so staff still have a starting point (reason says why).
        for advisor in advisors:
            if not advisor.get("active", True) or not advisor.get("available", True):
                continue
            capacity = _capacity(advisor)
            modes = list(advisor.get("meeting_mode", []))
            pref_match = bool(preference) and preference in modes
            score = 10.0 + (2 if pref_match else 0) + min(capacity, 6) * 0.5
            reasons = [
                "General request; no specialty required. Available for a new case.",
                f"Capacity: {capacity} open slot{'s' if capacity != 1 else ''}.",
            ]
            if pref_match:
                reasons.append(f"Offers the client's preferred {preference.replace('_', ' ')} meetings.")
            reasons.append("State and license eligibility must be verified manually; not assessed by the model.")
            scored.append((score, {**advisor, "_reason": " ".join(reasons), "_existing": False}))

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
                "existing_client_relationship": bool(advisor["_existing"]),
                "meeting_mode": list(advisor.get("meeting_mode", [])),
                "capacity": advisor.get("capacity"),
                "rank": rank,
                "active": bool(advisor.get("active", True)),
                "region": advisor.get("region"),
                "kind": str(advisor.get("kind") or "advisor"),
                "eligibility_check": "manual_verification_required",
            }
        )
    return candidates
