"""What a client can see and do on their own requests after intake.

Only the client-safe view leaves this module: the confirmed request, where it
stands, and the messages exchanged with the advisor. Staff notes, flags, and
routing never do.
"""

from __future__ import annotations

from typing import Any

from backend.errors import ApiError
from backend.schemas import CaseRecord
from backend.services.common import clean_text, now_iso
from backend.services.priority import lifecycle_of
from backend.store import Store

# An approved prepared action carries the message the advisor signed off; a bare approval has no text.
_MESSAGE_EVENTS = {"clarification_requested": "advisor", "action_approved": "advisor", "client_replied": "client"}


class ClientRequests:
    def __init__(self, store: Store):
        self.store = store

    @staticmethod
    def view(case: dict[str, Any]) -> dict[str, Any]:
        messages = [
            {"from": _MESSAGE_EVENTS[h["event"]], "text": h["details"]["text"], "at": h["at"]}
            for h in case.get("history") or []
            if h.get("event") in _MESSAGE_EVENTS and (h.get("details") or {}).get("text")
        ]
        lifecycle = lifecycle_of(case)
        return {
            "case_id": case["case_id"],
            "created_at": case["created_at"],
            "request": case["confirmed_plain_language_request"],
            "lifecycle": lifecycle,
            # A resolved request no longer needs the client's answer, whatever was asked before.
            "awaiting_reply": case["status"] == "needs_client_followup" and lifecycle != "resolved",
            "messages": messages,
        }

    def list(self, client_id: str) -> list[dict[str, Any]]:
        return [self.view(c) for c in self.store.list_cases() if c["client_id"] == client_id]

    def reply(self, client_id: str, case_id: str, text: str | None) -> dict[str, Any]:
        """Record the client's answer and hand the case back to whoever was working on it."""
        with self.store.lock:
            case = self.store.get_case(case_id)
            if not case:
                raise ApiError(404, "CASE_NOT_FOUND", f"No such fictional case {case_id!r}.")
            if case["client_id"] != client_id:
                raise ApiError(403, "WRONG_DEMO_CLIENT", "This request belongs to a different client (simulated access control).")
            if not self.view(case)["awaiting_reply"]:
                raise ApiError(409, "NOT_AWAITING_REPLY", "This request is not waiting on an answer from you.")
            text = clean_text(text, "Your answer")
            if not text:
                raise ApiError(400, "MISSING_TEXT", "Type your answer before sending.")
            now = now_iso()
            case.setdefault("history", []).append({"event": "client_replied", "at": now, "details": {"by": client_id, "text": text}})
            case["status"] = "assigned" if case["routing"].get("assigned_advisor_id") else "staff_review"
            case["updated_at"] = now
            self.store.save_case(CaseRecord.model_validate(case).model_dump())
        return self.view(case)
