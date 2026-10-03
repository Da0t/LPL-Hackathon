"""Staff queue, case document, candidate ranking, and human assignment (Agent 2)."""

from __future__ import annotations

import logging
from typing import Any

from backend.errors import ApiError
from backend.schemas import CaseRecord, SECURITY_DESTINATION
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
            raise ApiError(404, "CASE_NOT_FOUND", f"No such fictional case {case_id!r}.")
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
            "urgency": case.get("urgency") or {"level": "none", "reason": None},
            "clarification_needed": bool(case.get("unresolved_questions")) or case.get("account_match_status") == "unresolved",
            "existing_advisor_id": case.get("existing_advisor_id"),
            "routing": {"destination": case["routing"]["destination"], "assigned_advisor_id": case["routing"].get("assigned_advisor_id")},
        }

    def get_case(self, case_id: str, mark_reviewed: bool = True) -> dict[str, Any]:
        with self.store.lock:
            case = self._case(case_id)
            if mark_reviewed and case["status"] == "submitted":
                now = now_iso()
                case["status"] = "staff_review"
                case["updated_at"] = now
                case.setdefault("history", []).append({"event": "staff_review_started", "at": now, "details": {"by": "staff-demo"}})
                self.store.save_case(case)
        return CaseRecord.model_validate(case).model_dump()

    def candidates(self, case_id: str) -> dict[str, Any]:
        case = self._case(case_id)
        client = self.store.get_client(case["client_id"])
        destination = case["routing"]["destination"]
        ranked = routing.rank_advisors(self.store.list_advisors(), case["categories"], client, case.get("existing_advisor_id"), destination)
        reason = case["routing"].get("reason")
        if destination == SECURITY_DESTINATION and not ranked:
            queue = next((q for q in self.store.specialist_queues if q.get("destination") == destination), None)
            name = (queue or {}).get("display_name") or "Security specialist review queue"
            reason = f"{name}: possible unauthorized access or fraud. Advisor matching is turned off; staff route this request to the specialist queue."
        return {"candidates": ranked, "case_id": case_id, "destination": destination, "reason": reason}

    # ---- advisor workspace (additive; brief is read-only, actions use history) ----

    def brief(self, case_id: str, ai_mode: str = "mock") -> dict[str, Any]:
        """Read-only Bedrock-generated advisor prep brief. Never mutates the case."""
        case = self._case(case_id)
        from backend.aws import bedrock_agent as ba  # local import keeps layering light
        note = None
        if ai_mode == "bedrock":
            try:
                raw = ba.advisor_brief(case)
            except Exception as exc:  # noqa: BLE001 , fall back so the demo never dead-ends
                log.warning("advisor_brief fell back to offline: %s", exc)
                raw = ba._stub_brief(case)
                note = "Generated offline (model temporarily unavailable)."
        else:
            raw = ba._stub_brief(case)
            note = "Deterministic brief (set SAMEPAGE_AI_MODE=bedrock for the live model)."
        return {"case_id": case_id, "ai_mode": ai_mode, "note": note, **raw}

    _ACTIONS = {
        "claim": "advisor_claimed",
        "note": "advisor_note",
        "clarify": "clarification_requested",
        "schedule": "meeting_scheduled",
        "resolve": "request_resolved",
    }

    def action(self, case_id: str, action: str, text: str | None = None) -> dict[str, Any]:
        """Record an advisor action as a history event. 'clarify' moves the case to
        needs_client_followup; others keep the status and are derived from history."""
        event_name = self._ACTIONS.get(action)
        if not event_name:
            raise ApiError(400, "INVALID_ACTION", f"Unknown advisor action {action!r}.")
        if action in ("note", "clarify", "resolve") and not (text or "").strip():
            raise ApiError(400, "MISSING_TEXT", f"The '{action}' action needs text.")
        with self.store.lock:
            case = self._case(case_id)
            now = now_iso()
            details: dict[str, Any] = {"by": "advisor-demo"}
            if text:
                details["text"] = text.strip()
            event = {"event": event_name, "at": now, "details": details}
            case.setdefault("history", []).append(event)
            if action == "clarify":
                case["status"] = "needs_client_followup"
            case["updated_at"] = now
            self.store.save_case(CaseRecord.model_validate(case).model_dump())
        return {"case_id": case_id, "status": case["status"], "event": event}

    def assign(self, case_id: str, advisor_id: str, staff_reason: str) -> dict[str, Any]:
        with self.store.lock:
            return self._assign(case_id, advisor_id, staff_reason)

    def _assign(self, case_id: str, advisor_id: str, staff_reason: str) -> dict[str, Any]:
        case = self._case(case_id)
        reason = (staff_reason or "").strip()
        if not reason:
            raise ApiError(400, "INVALID_ASSIGNMENT", "Case, advisor, and staff reason are required.")
        advisor = self.store.get_advisor(advisor_id)
        if not advisor:
            raise ApiError(404, "ADVISOR_NOT_FOUND", f"No advisor {advisor_id!r} in the fictional directory.")
        if not advisor.get("active", True):
            raise ApiError(409, "ADVISOR_NOT_ACTIVE", f"{advisor['display_name']} is not active and cannot be assigned.")

        now = now_iso()
        new_flags: list[str] = []
        if case["routing"]["destination"] == SECURITY_DESTINATION and "fraud_or_security" not in advisor.get("specialties", []):
            new_flags.append("staff_overrode_specialist_recommendation")
        if advisor_id not in case["routing"].get("recommended_advisor_ids", []):
            new_flags.append("staff_overrode_recommendation")
        for flag in new_flags:
            if flag not in case["flags"]:
                case["flags"].append(flag)

        previous = case["routing"].get("assigned_advisor_id")
        case["routing"]["assigned_advisor_id"] = advisor_id
        case["routing"]["staff_decision"] = reason
        case["routing"]["staff_decision_detail"] = {"advisor_id": advisor_id, "staff_reason": reason, "decided_at": now, "decided_by": "staff-demo"}
        case["status"] = "assigned"
        case["updated_at"] = now
        case.setdefault("history", []).append(
            {"event": "assigned" if not previous else "reassigned", "at": now,
             "details": {"advisor_id": advisor_id, "previous_advisor_id": previous, "staff_reason": reason, "flags_added": new_flags}}
        )
        self.store.save_case(CaseRecord.model_validate(case).model_dump())
        self.store.record_assignment(case_id, advisor_id, reason, "staff-demo", now)
        log.info("case %s assigned to %s (no outbound message, transaction, or appointment is created)", case_id, advisor_id)
        return {"case_id": case_id, "status": "assigned", "assigned_advisor_id": advisor_id, "flags": case["flags"]}
