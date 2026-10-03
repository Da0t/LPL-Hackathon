"""Intake session state machine (Agent 2).

States: ``draft`` -> ``needs_clarification`` | ``ready_for_client_review`` -> ``submitted``.

Rules enforced here, independent of the language model:
* The session binds one synthetic client; every lookup is scoped to it.
* A model suggestion is a proposal. ``selected_account_id`` becomes set only when
  the client picks an option carrying an account or chooses an account on the
  review screen. The model's own guess is exposed as ``candidate_account_id``.
* An amount is confirmed only when the client submits it on the review screen.
* A model or AWS failure preserves the draft and returns a useful message.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.errors import ApiError
from backend.schemas import (
    MAX_TEXT_CHARS,
    OPTION_NONE_OF_THESE,
    OPTION_TALK_TO_PERSON,
    RESERVED_OPTION_IDS,
    normalize_input_mode,
)
from backend.services.agent_adapter import AdapterError, AdapterTimeout, AgentAdapter
from backend.services.common import new_session_id, now_iso
from backend.services.tools import build_tools
from backend.services.triage import build_case
from backend.services.validation import validate_intake_output
from backend.store import Store

log = logging.getLogger("samepage.intake")

DEGRADED_MESSAGE = (
    "We couldn't process that just now, but your words are saved. You can keep typing, "
    "try again in a moment, or choose 'Talk to a person' and we will pass along what you have written."
)


def _fallback_proposal(transcript: str) -> str:
    text = transcript.strip()
    return f"I would like to speak with an advisor about this: \"{text}\"" if text else "I would like to speak with an advisor."


class IntakeService:
    def __init__(self, store: Store, adapter: AgentAdapter):
        self.store = store
        self.adapter = adapter

    # ----------------------------------------------------------------- start

    def start(self, client_id: str) -> dict[str, Any]:
        client = self.store.get_client(client_id)
        if not client:
            raise ApiError(404, "client_not_found", f"No synthetic demo client with id {client_id!r}.")
        now = now_iso()
        session = {
            "session_id": new_session_id(),
            "client_id": client["client_id"],
            "client_display_name": client["display_name"],
            "status": "draft",
            "created_at": now,
            "updated_at": now,
            "transcript": "",
            "input_modes": [],
            "turns": [],
            "selected_account_id": None,
            "candidate_account_id": None,
            "candidate_intent": None,
            "proposed_plain_language_request": None,
            "uncertainties": [],
            "offered_account_ids": [],
            "client_requested_person": False,
            "last_suggestions": [],
            "last_question": None,
            "last_selected_option": None,
            "case_id": None,
            "adapter_errors": 0,
        }
        self.store.save_session(session)
        return session

    def get_session(self, session_id: str) -> dict[str, Any]:
        session = self.store.get_session(session_id)
        if not session:
            raise ApiError(404, "session_not_found", f"No intake session {session_id!r}. Start one with POST /intake/start.")
        return session

    # --------------------------------------------------------------- context

    @staticmethod
    def session_context(session: dict[str, Any]) -> dict[str, Any]:
        """What the adapter may learn about the conversation so far (no account facts)."""
        return {
            "session_id": session["session_id"],
            "client_id": session["client_id"],
            "status": session["status"],
            "turn_count": len(session["turns"]),
            "transcript": session["transcript"],
            "selected_account_id": session["selected_account_id"],
            "candidate_account_id": session["candidate_account_id"],
            "candidate_intent": session["candidate_intent"],
            "client_requested_person": session["client_requested_person"],
            "offered_account_ids": list(session["offered_account_ids"]),
            "last_question": session["last_question"],
            "last_suggestions": list(session["last_suggestions"]),
            "last_selected_option": session["last_selected_option"],
            "turns": [
                {
                    "turn_number": t["turn_number"],
                    "text": t["text"],
                    "selected_option_id": t.get("selected_option_id"),
                    "selected_option_label": t.get("selected_option_label"),
                    "question": t.get("question"),
                    "suggestions": t.get("suggestions", []),
                    "candidate_intent": t.get("candidate_intent"),
                    "uncertainty": t.get("uncertainty"),
                }
                for t in session["turns"]
            ],
        }

    # ------------------------------------------------------------------ turn

    def turn(self, session_id: str, text: str, input_mode: str, selected_option_id: str | None) -> dict[str, Any]:
        session = self.get_session(session_id)
        if session["status"] == "submitted":
            raise ApiError(409, "session_already_submitted", "This request was already confirmed and sent.", {"case_id": session["case_id"]})

        text = (text or "").strip()
        if len(text) > MAX_TEXT_CHARS:
            raise ApiError(400, "text_too_long", f"Text must be {MAX_TEXT_CHARS} characters or fewer.")
        selected_option_id = (selected_option_id or "").strip() or None
        if not text and not selected_option_id:
            raise ApiError(400, "empty_turn", "Send some text, a selected_option_id, or both.")

        # Validate the option against what the client was actually shown.
        selected_option: dict[str, Any] | None = None
        if selected_option_id:
            shown = {s["id"]: s for s in session["last_suggestions"]}
            if selected_option_id in shown:
                selected_option = shown[selected_option_id]
            elif selected_option_id not in RESERVED_OPTION_IDS:
                raise ApiError(
                    400,
                    "invalid_option",
                    f"selected_option_id {selected_option_id!r} is not one of the options shown on the last turn.",
                    {"valid_option_ids": list(shown) + list(RESERVED_OPTION_IDS)},
                )

        mode = normalize_input_mode(input_mode)
        if text:
            session["transcript"] = text
            if mode not in session["input_modes"]:
                session["input_modes"].append(mode)
        transcript = session["transcript"]
        if not transcript:
            raise ApiError(400, "empty_turn", "Please describe what you need help with before choosing an option.")

        # Deterministic handling of the client's explicit choice.
        if selected_option:
            session["last_selected_option"] = {"id": selected_option["id"], "label": selected_option["label"], "account_id": selected_option.get("account_id")}
            if selected_option.get("account_id"):
                session["selected_account_id"] = selected_option["account_id"]
        elif selected_option_id == OPTION_NONE_OF_THESE:
            session["last_selected_option"] = {"id": OPTION_NONE_OF_THESE, "label": "None of these", "account_id": None}
            session["selected_account_id"] = None
            session["candidate_account_id"] = None
        elif selected_option_id == OPTION_TALK_TO_PERSON:
            session["last_selected_option"] = {"id": OPTION_TALK_TO_PERSON, "label": "Talk to a person", "account_id": None}
            session["client_requested_person"] = True

        owned_ids = {a["account_id"] for a in self.store.accounts_for_client(session["client_id"])}
        tools = build_tools(self.store, session["client_id"], lambda: self.session_context(session))

        degraded = False
        message: str | None = None
        try:
            raw = self.adapter.intake_turn(session["client_id"], transcript, selected_option_id, tools)
            validated = validate_intake_output(raw, owned_ids, self.store.glossary_lookup)
        except AdapterTimeout as exc:
            degraded, message = True, DEGRADED_MESSAGE
            session["adapter_errors"] += 1
            log.warning("intake adapter timeout (session %s): %s", session_id, exc)
            validated = None
        except AdapterError as exc:
            degraded, message = True, DEGRADED_MESSAGE
            session["adapter_errors"] += 1
            log.warning("intake adapter error (session %s): %s", session_id, type(exc.__cause__ or exc).__name__)
            validated = None

        turn_number = len(session["turns"]) + 1
        if validated is not None:
            if validated["notes"]:
                log.info("intake validation notes (session %s): %s", session_id, "; ".join(validated["notes"]))
            session["last_suggestions"] = validated["suggestions"]
            session["last_question"] = validated["question"]
            session["candidate_account_id"] = validated["candidate_account_id"]
            if validated["candidate_intent"]:
                session["candidate_intent"] = validated["candidate_intent"]
            if validated["proposed_plain_language_request"]:
                session["proposed_plain_language_request"] = validated["proposed_plain_language_request"]
            if validated["uncertainty"] and validated["uncertainty"] not in session["uncertainties"]:
                session["uncertainties"].append(validated["uncertainty"])
            for suggestion in validated["suggestions"]:
                if suggestion.get("account_id") and suggestion["account_id"] not in session["offered_account_ids"]:
                    session["offered_account_ids"].append(suggestion["account_id"])
            if validated["candidate_account_id"] and validated["candidate_account_id"] not in session["offered_account_ids"]:
                session["offered_account_ids"].append(validated["candidate_account_id"])
            suggestions = validated["suggestions"]
            question = validated["question"]
            definitions = validated["definitions"]
            uncertainty = validated["uncertainty"]
        else:
            # Preserve the draft: keep the last options so the client can still pick one.
            suggestions = session["last_suggestions"]
            question = session["last_question"]
            definitions = []
            uncertainty = None

        if session["client_requested_person"]:
            status = "ready_for_client_review"
        elif degraded:
            status = "needs_clarification"
        elif question:
            status = "needs_clarification"
        else:
            status = "ready_for_client_review"
        session["status"] = status

        if not session["proposed_plain_language_request"] and status == "ready_for_client_review":
            session["proposed_plain_language_request"] = _fallback_proposal(transcript)

        now = now_iso()
        session["turns"].append(
            {
                "turn_number": turn_number,
                "text": transcript,
                "input_mode": mode,
                "selected_option_id": selected_option_id,
                "selected_option_label": (session["last_selected_option"] or {}).get("label") if selected_option_id else None,
                "suggestions": suggestions,
                "question": question,
                "uncertainty": uncertainty,
                "candidate_intent": session["candidate_intent"],
                "candidate_account_id": session["candidate_account_id"],
                "degraded": degraded,
                "at": now,
            }
        )
        session["updated_at"] = now
        self.store.save_session(session)

        return {
            "session_id": session["session_id"],
            "transcript": transcript,
            "suggestions": suggestions,
            "question": question,
            "definitions": definitions,
            "candidate_intent": session["candidate_intent"],
            "selected_account_id": session["selected_account_id"],
            "uncertainty": uncertainty,
            "status": status,
            "candidate_account_id": session["candidate_account_id"],
            "proposed_plain_language_request": session["proposed_plain_language_request"],
            "message": message,
            "degraded": degraded,
            "turn_number": turn_number,
        }

    # --------------------------------------------------------------- confirm

    def confirm(
        self,
        session_id: str,
        confirmed_plain_language_request: str,
        selected_account_id: str | None,
        amount_requested: float | None,
    ) -> dict[str, Any]:
        session = self.get_session(session_id)
        if session["status"] == "submitted":
            raise ApiError(409, "session_already_submitted", "This request was already confirmed and sent.", {"case_id": session["case_id"]})
        if not session["transcript"].strip():
            raise ApiError(409, "nothing_to_confirm", "Describe your request with at least one turn before confirming.")
        wording = (confirmed_plain_language_request or "").strip()
        if not wording:
            raise ApiError(400, "empty_confirmation", "confirmed_plain_language_request cannot be empty.")

        selected_account = None
        if selected_account_id:
            owned = {a["account_id"]: a for a in self.store.accounts_for_client(session["client_id"])}
            if selected_account_id not in owned:
                log.warning("confirm refused: session %s (client %s) asked for account %s", session_id, session["client_id"], selected_account_id)
                raise ApiError(403, "account_not_authorized", "That account is not part of this client's authorized records.")
            selected_account = owned[selected_account_id]

        if amount_requested is not None:
            if amount_requested <= 0:
                raise ApiError(400, "invalid_amount", "amount_requested must be greater than zero.")
            if float(amount_requested).is_integer():
                amount_requested = int(amount_requested)

        case = build_case(
            store=self.store,
            adapter=self.adapter,
            session=session,
            confirmed_plain_language_request=wording,
            selected_account=selected_account,
            amount_requested=amount_requested,
        )
        self.store.save_case(case)

        now = now_iso()
        session["status"] = "submitted"
        session["case_id"] = case["case_id"]
        session["updated_at"] = now
        self.store.save_session(session)

        return {
            "case_id": case["case_id"],
            "status": case["status"],
            "client_summary": case["confirmed_plain_language_request"],
            "next_step": (
                "Your request has been sent to our team for review. A staff member will read your words and your "
                "confirmed request before deciding who should contact you. Nothing has been changed on your accounts."
            ),
        }
