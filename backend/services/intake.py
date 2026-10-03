"""Intake session state machine (Agent 2).

States: ``draft`` -> ``needs_clarification`` | ``ready_for_client_review`` -> ``submitted``.

Rules enforced here, independent of the language model:
* The session binds one synthetic client; every lookup is scoped to it.
* A model suggestion is a proposal. ``selected_account_id`` becomes set only when the
  client picks an option carrying an account or chooses an account on the review
  screen. The model's own guess is exposed as ``candidate_account_id``.
* An amount is confirmed only when the client submits it on the review screen.
* A model or AWS failure preserves the draft and returns a useful message.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from backend.errors import ApiError
from backend.schemas import (
    CONFIRM_CLIENT_SUMMARY_DEFAULT,
    MAX_TEXT_CHARS,
    OPTION_NONE_OF_THESE,
    OPTION_TALK_TO_PERSON,
    RESERVED_OPTION_IDS,
    normalize_input_mode,
)
from backend.services.agent_adapter import AdapterError, AdapterTimeout, AgentAdapter
from backend.services.common import new_session_id, now_iso
from backend.services.text_rules import mentioned_account_types
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
        self._locks_guard = threading.Lock()
        self._session_locks: dict[str, threading.Lock] = {}

    def _session_lock(self, session_id: str) -> threading.Lock:
        """One lock per session so overlapping turns/confirms cannot lose each other's writes."""
        with self._locks_guard:
            lock = self._session_locks.get(session_id)
            if lock is None:
                lock = self._session_locks[session_id] = threading.Lock()
            return lock

    # ----------------------------------------------------------------- start

    def start(self, client_id: str) -> dict[str, Any]:
        client = self.store.get_client(client_id)
        if not client:
            raise ApiError(404, "CLIENT_NOT_FOUND", f"No authorized fictional client with id {client_id!r}.")
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
            raise ApiError(404, "SESSION_NOT_FOUND", f"No intake session {session_id!r}. Start one with POST /intake/start.")
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
                    "turn_number": t["turn_number"], "text": t["text"], "selected_option_id": t.get("selected_option_id"),
                    "selected_option_label": t.get("selected_option_label"), "question": t.get("question"),
                    "suggestions": t.get("suggestions", []), "candidate_intent": t.get("candidate_intent"), "uncertainty": t.get("uncertainty"),
                }
                for t in session["turns"]
            ],
        }

    # ------------------------------------------------------------------ turn

    def turn(self, session_id: str, text: str, input_mode: str, selected_option_id: str | None) -> dict[str, Any]:
        with self._session_lock(session_id):
            return self._turn(session_id, text, input_mode, selected_option_id)

    def _turn(self, session_id: str, text: str, input_mode: str, selected_option_id: str | None) -> dict[str, Any]:
        received_at = now_iso()
        session = self.get_session(session_id)
        if session["status"] == "submitted":
            raise ApiError(409, "SESSION_ALREADY_SUBMITTED", "This request was already confirmed and sent.", {"case_id": session["case_id"]})

        text = (text or "").strip()
        if len(text) > MAX_TEXT_CHARS:
            raise ApiError(400, "INVALID_TURN", f"Text must be {MAX_TEXT_CHARS} characters or fewer.")
        selected_option_id = (selected_option_id or "").strip() or None
        if not text and not selected_option_id:
            raise ApiError(400, "INVALID_TURN", "Send some text, a selected_option_id, or both.")

        selected_option: dict[str, Any] | None = None
        if selected_option_id:
            shown = {s["id"]: s for s in session["last_suggestions"]}
            if selected_option_id in RESERVED_OPTION_IDS:
                selected_option = None  # reserved semantics always win over a model-supplied id
            elif selected_option_id in shown:
                selected_option = shown[selected_option_id]
            else:
                raise ApiError(
                    400, "INVALID_OPTION",
                    f"selected_option_id {selected_option_id!r} is not one of the options shown on the last turn.",
                    {"valid_option_ids": list(shown) + list(RESERVED_OPTION_IDS)},
                )

        mode = normalize_input_mode(input_mode)
        if text:
            if text != session["transcript"]:
                if session["client_requested_person"] and selected_option_id != OPTION_TALK_TO_PERSON:
                    session["client_requested_person"] = False  # the client kept talking; resume clarification
                selected = session.get("selected_account_id")
                if selected and not selected_option:
                    # The client changed their words after picking an account. If the new words name a
                    # different account type they own, demote the pick to a proposal so it is re-confirmed.
                    owned = {a["account_id"]: a for a in self.store.accounts_for_client(session["client_id"])}
                    picked_type = (owned.get(selected) or {}).get("account_type")
                    named = mentioned_account_types(text)
                    owned_types = {a.get("account_type") for a in owned.values()}
                    if named and picked_type not in named and any(t in owned_types for t in named):
                        session["candidate_account_id"] = selected
                        session["selected_account_id"] = None
            session["transcript"] = text
            if mode not in session["input_modes"]:
                session["input_modes"].append(mode)
        transcript = session["transcript"]
        if not transcript:
            raise ApiError(400, "INVALID_TURN", "Please describe what you need help with before choosing an option.")

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
        validated: dict[str, Any] | None = None
        try:
            raw = self.adapter.intake_turn(session["client_id"], transcript, selected_option_id, tools)
            validated = validate_intake_output(raw, owned_ids, self.store.glossary_lookup)
        except AdapterTimeout as exc:
            degraded, message = True, DEGRADED_MESSAGE
            session["adapter_errors"] += 1
            log.warning("intake adapter timeout (session %s): %s", session_id, exc.code)
        except AdapterError as exc:
            degraded, message = True, (exc.user_message or DEGRADED_MESSAGE)
            session["adapter_errors"] += 1
            log.warning("intake adapter error (session %s): %s", session_id, exc.code)

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
            suggestions, question, definitions, uncertainty = validated["suggestions"], validated["question"], validated["definitions"], validated["uncertainty"]
        else:
            # Preserve the draft: keep the last options so the client can still pick one.
            suggestions, question, definitions, uncertainty = session["last_suggestions"], session["last_question"], [], None

        if session["client_requested_person"]:
            status = "ready_for_client_review"
        elif degraded or question:
            status = "needs_clarification"
        else:
            status = "ready_for_client_review"
        session["status"] = status
        if not session["proposed_plain_language_request"] and status == "ready_for_client_review":
            session["proposed_plain_language_request"] = _fallback_proposal(transcript)

        now = now_iso()
        session["turns"].append(
            {
                "turn_number": turn_number, "text": transcript, "input_mode": mode, "selected_option_id": selected_option_id,
                "selected_option_label": (session["last_selected_option"] or {}).get("label") if selected_option_id else None,
                "suggestions": suggestions, "question": question, "uncertainty": uncertainty,
                "candidate_intent": session["candidate_intent"], "candidate_account_id": session["candidate_account_id"],
                "degraded": degraded, "received_at": received_at, "at": now,
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

    def confirm(self, session_id: str, confirmed_plain_language_request: str, selected_account_id: str | None, amount_requested: float | None) -> dict[str, Any]:
        with self._session_lock(session_id):
            return self._confirm(session_id, confirmed_plain_language_request, selected_account_id, amount_requested)

    def _confirm(self, session_id: str, confirmed_plain_language_request: str, selected_account_id: str | None, amount_requested: float | None) -> dict[str, Any]:
        session = self.get_session(session_id)
        if session["status"] == "submitted":
            raise ApiError(409, "SESSION_ALREADY_SUBMITTED", "This request was already confirmed and sent.", {"case_id": session["case_id"]})
        if not session["transcript"].strip():
            raise ApiError(409, "NOTHING_TO_CONFIRM", "Describe your request with at least one turn before confirming.")
        wording = (confirmed_plain_language_request or "").strip()
        if not wording:
            raise ApiError(400, "MISSING_CONFIRMATION", "Confirm the request in your own words.")

        selected_account = None
        if selected_account_id:
            owned = {a["account_id"]: a for a in self.store.accounts_for_client(session["client_id"])}
            if selected_account_id not in owned:
                log.warning("confirm refused: session %s (client %s) asked for account %s", session_id, session["client_id"], selected_account_id)
                raise ApiError(403, "ACCOUNT_MISMATCH", "That account is not part of this client's authorized records.")
            selected_account = owned[selected_account_id]

        if amount_requested is not None:
            if amount_requested <= 0:
                raise ApiError(400, "INVALID_AMOUNT", "amount_requested must be greater than zero.")
            if float(amount_requested).is_integer():
                amount_requested = int(amount_requested)

        case = build_case(
            store=self.store, adapter=self.adapter, session=session,
            confirmed_plain_language_request=wording, selected_account=selected_account, amount_requested=amount_requested,
        )
        client_summary = case.pop("_client_summary", None) or CONFIRM_CLIENT_SUMMARY_DEFAULT
        if getattr(self, "portal", None):
            case["_portal_document"] = self.portal.document(
                session["client_id"], session["transcript"], wording,
                selected_account_id, amount_requested, case["case_id"],
            )
        self.store.insert_case(case)

        now = now_iso()
        session["status"] = "submitted"
        session["case_id"] = case["case_id"]
        session["updated_at"] = now
        self.store.save_session(session)

        return {
            "case_id": case["case_id"],
            "status": case["status"],
            "client_summary": client_summary,
            "next_step": (
                "A staff member will read your words and your confirmed request before deciding who should contact you. "
                "Nothing has been changed on your accounts."
            ),
        }
