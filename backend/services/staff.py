"""Staff queue, case document, candidate ranking, and human assignment (Agent 2)."""

from __future__ import annotations

import logging
from typing import Any

from backend.errors import ApiError
from backend.schemas import CaseRecord
from backend.services import routing
from backend.services.common import now_iso
from backend.store import Store

log = logging.getLogger("samepage.staff")


class StaffService:
    def __init__(self, store: Store):
        self.store = store

    def _case(self, case_id: str) -> dict[str, Any]:
        case = self.store.get_case(case_id)
        if not case:
            raise ApiError(404, "case_not_found", f"No case {case_id!r}.")
        return case

    def list_cases(self, status: str | None = None, category: str | None = None) -> list[dict[str, Any]]:
        cases = self.store.list_cases()
        if status:
            cases = [c for c in cases if c["status"] == status]
        if category:
            cases = [c for c in cases if category in c.get("categories", [])]
        return [self.summary(c) for c in cases]

    @staticmethod
    def summary(case: dict[str, Any]) -> dict[str, Any]:
        return {
            "case_id": case["case_id"],
            "client_display_name": case["client_display_name"],
            "created_at": case["created_at"],
            "status": case["status"],
            "categories": case["categories"],
            "flags": case["flags"],
            "confirmed_plain_language_request": case["confirmed_plain_language_request"],
            "client_id": case["client_id"],
            "urgency": case["urgency"],
            "clarification_needed": bool(case.get("unresolved_questions")) or case.get("account_match_status") == "unresolved",
            "existing_advisor_id": case.get("existing_advisor_id"),
            "destination": case["routing"]["destination"],
            "assigned_advisor_id": case["routing"].get("assigned_advisor_id"),
        }

    def get_case(self, case_id: str, mark_reviewed: bool = True) -> dict[str, Any]:
        case = self._case(case_id)
        if mark_reviewed and case["status"] == "submitted":
            now = now_iso()
            case["status"] = "staff_review"
            case["updated_at"] = now
            case["history"].append({"event": "staff_review_started", "at": now, "details": {"by": "staff-demo"}})
            self.store.save_case(case)
        return CaseRecord.model_validate(case).model_dump()

    def candidates(self, case_id: str) -> dict[str, Any]:
        case = self._case(case_id)
        client = self.store.get_client(case["client_id"])
        destination = case["routing"]["destination"]
        ranked = routing.rank_advisors(
            self.store.list_advisors(), case["categories"], client, case.get("existing_advisor_id"), destination
        )
        return {
            "candidates": ranked,
            "case_id": case_id,
            "destination": destination,
            "destination_reason": case["routing"].get("destination_reason"),
        }

    def assign(self, case_id: str, advisor_id: str, staff_reason: str) -> dict[str, Any]:
        case = self._case(case_id)
        reason = (staff_reason or "").strip()
        if not reason:
            raise ApiError(400, "staff_reason_required", "Record a short reason for the assignment.")
        advisor = self.store.get_advisor(advisor_id)
        if not advisor:
            raise ApiError(404, "advisor_not_found", f"No advisor {advisor_id!r} in the fictional directory.")
        if not advisor.get("active", True):
            raise ApiError(409, "advisor_not_active", f"{advisor['display_name']} is not active and cannot be assigned.")

        now = now_iso()
        new_flags: list[str] = []
        if case["routing"]["destination"] == routing.SPECIALIST_DESTINATION and "fraud_or_security" not in advisor.get("specialties", []):
            new_flags.append("staff_overrode_specialist_recommendation")
        if advisor_id not in case["routing"].get("recommended_advisor_ids", []):
            new_flags.append("staff_overrode_recommendation")
        for flag in new_flags:
            if flag not in case["flags"]:
                case["flags"].append(flag)

        previous = case["routing"].get("assigned_advisor_id")
        case["routing"]["assigned_advisor_id"] = advisor_id
        case["routing"]["staff_decision"] = {
            "advisor_id": advisor_id,
            "staff_reason": reason,
            "decided_at": now,
            "decided_by": "staff-demo",
        }
        case["status"] = "assigned"
        case["updated_at"] = now
        case["history"].append(
            {
                "event": "assigned" if not previous else "reassigned",
                "at": now,
                "details": {"advisor_id": advisor_id, "previous_advisor_id": previous, "staff_reason": reason, "flags_added": new_flags},
            }
        )
        self.store.save_case(CaseRecord.model_validate(case).model_dump())
        self.store.record_assignment(case_id, advisor_id, reason, "staff-demo", now)
        log.info("case %s assigned to %s (no outbound message, transaction, or appointment is created)", case_id, advisor_id)
        return {"case_id": case_id, "status": "assigned", "assigned_advisor_id": advisor_id, "flags": case["flags"]}
