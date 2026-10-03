"""Staff queue, case document, candidate ranking, and human assignment (Agent 2)."""

from __future__ import annotations

import logging
from typing import Any, Callable

from backend.errors import ApiError
from backend.schemas import CaseRecord, SECURITY_DESTINATION
from backend.services import routing
from backend.services.priority import intake_metrics, lifecycle_of, priority_for
from backend.services.common import now_iso
from backend.services.reply_workflow import run_reply_workflow
from backend.store import Store

log = logging.getLogger("samepage.staff")


class StaffService:
    def __init__(self, store: Store):
        self.store = store
        self._agent_cache: dict[tuple[str, str], tuple[Any, dict[str, Any], str | None]] = {}
        self._verdicts: dict[tuple[str, str], str] = {}  # (case_id, message text) -> compliance verdict

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
            "priority": priority_for(case),
            "lifecycle": lifecycle_of(case),
            "intake": intake_metrics(case),
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

    def _cached(self, kind: str, case: dict[str, Any], ai_mode: str, refresh: bool,
                produce: Callable[[], tuple[dict[str, Any], str | None]]) -> tuple[dict[str, Any], str | None]:
        """Reuse an agent's last answer for a case until the case changes or the advisor regenerates.
        A live-mode fallback is never kept, so the model is tried again on the next view."""
        slot, version = (kind, case["case_id"]), case.get("updated_at")
        hit = self._agent_cache.get(slot)
        if hit and hit[0] == version and not refresh:
            return hit[1], hit[2]
        result, note = produce()
        if ai_mode != "bedrock" or note is None:
            self._agent_cache[slot] = (version, result, note)
        return result, note

    def brief(self, case_id: str, ai_mode: str = "mock", refresh: bool = False) -> dict[str, Any]:
        """Read-only Bedrock-generated advisor prep brief. Never mutates the case."""
        case = self._case(case_id)
        from backend.aws import bedrock_agent as ba  # local import keeps layering light
        raw, note = self._cached("brief", case, ai_mode, refresh, lambda: self._run_agent(
            ai_mode, lambda: ba.advisor_brief(case), lambda: ba._stub_brief(case), "brief"))
        return {"case_id": case_id, "ai_mode": ai_mode, "note": note, **raw}

    def plan(self, case_id: str, ai_mode: str = "mock") -> dict[str, Any]:
        """Read-only agentic action packet: pre-filled fields + compliance checks +
        client/advisor drafts, for human approval. Never mutates the case."""
        case = self._case(case_id)
        from backend.aws import bedrock_agent as ba
        note = None
        if ai_mode == "bedrock":
            try:
                raw = ba.fulfillment_plan(case)
            except Exception as exc:  # noqa: BLE001
                log.warning("fulfillment_plan fell back to offline: %s", exc)
                raw = ba._stub_plan(case)
                note = "Prepared offline (model temporarily unavailable)."
        else:
            raw = ba._stub_plan(case)
            note = "Deterministic plan (set SAMEPAGE_AI_MODE=bedrock for the live agent)."
        return {"case_id": case_id, "ai_mode": ai_mode, "note": note, **raw}

    def _agent_facts(self, case: dict[str, Any]) -> dict[str, Any]:
        """The case plus the approved plain-language definition of its account type, if any."""
        ac = case.get("account_context") or {}
        entry = self.store.glossary_lookup(str(ac.get("account_label") or ac.get("account_type") or "").replace("_", " "))
        glossary = [{"term": entry["term"], "plain": entry.get("plain")}] if entry else []
        client = self.store.get_client(case["client_id"]) or {}
        return {**case, "glossary": glossary, "client_meeting_preference": client.get("meeting_preference")}

    @staticmethod
    def _run_agent(ai_mode: str, live: Callable[[], dict[str, Any]], offline: Callable[[], dict[str, Any]], what: str) -> tuple[dict[str, Any], str | None]:
        """Run an advisor agent live in bedrock mode, falling back offline so the demo never dead-ends."""
        if ai_mode != "bedrock":
            return offline(), f"Deterministic {what} (set SAMEPAGE_AI_MODE=bedrock for the live model)."
        try:
            return live(), None
        except Exception as exc:  # noqa: BLE001
            log.warning("%s fell back to offline: %s", what, exc)
            return offline(), "Generated offline (model temporarily unavailable)."

    def next_steps(self, case_id: str, ai_mode: str = "mock", refresh: bool = False) -> dict[str, Any]:
        """Next-steps planner agent. Never mutates the case."""
        case = self._case(case_id)
        facts = self._agent_facts(case)
        from backend.aws import advisor_agents as aa
        result, note = self._cached("plan", case, ai_mode, refresh, lambda: self._run_agent(
            ai_mode, lambda: aa.plan_next_steps(facts), lambda: aa.stub_plan_next_steps(facts), "plan"))
        return {"case_id": case_id, "ai_mode": ai_mode, "note": note, **result}

    def _timeline(self, case: dict[str, Any]) -> list[dict[str, Any]]:
        """Every recorded event on the client's accounts, then the client's own report, oldest first."""
        entries = []
        for account in self.store.accounts_for_client(case["client_id"]):
            name = f"{account.get('label') or 'Account'} {account.get('masked_identifier') or ''}".strip()
            for e in self.store.events_for_account(account["account_id"]):
                entries.append({"date": e["date"], "type": e["type"], "label": e["type"].replace("_", " ").capitalize(),
                                "detail": e.get("summary") or e.get("description") or "", "account": name,
                                "source_id": e["source_id"], "highlight": e["type"] == "security_alert"})
        entries.append({"date": case["created_at"][:10], "type": "client_report", "label": "Client reported a concern",
                        "detail": case.get("original_words") or case["confirmed_plain_language_request"], "account": None,
                        "source_id": case["case_id"], "highlight": True})
        return sorted(entries, key=lambda t: t["date"])

    def investigation(self, case_id: str, ai_mode: str = "mock", refresh: bool = False) -> dict[str, Any]:
        """Fraud investigator agent for security cases. The timeline is record-built; never mutates the case."""
        case = self._case(case_id)
        if "fraud_or_security" not in case.get("categories", []):
            raise ApiError(400, "NOT_A_SECURITY_CASE", "The investigation is only available for security cases.")
        facts, timeline = self._agent_facts(case), self._timeline(case)
        from backend.aws import advisor_agents as aa
        result, note = self._cached("investigation", case, ai_mode, refresh, lambda: self._run_agent(
            ai_mode, lambda: aa.investigate_security(facts, timeline), lambda: aa.stub_investigate_security(facts, timeline), "assessment"))
        return {"case_id": case_id, "ai_mode": ai_mode, "note": note, "timeline": timeline, **result}

    def client_snapshot(self, case_id: str) -> dict[str, Any]:
        """The whole client behind a case, straight from the records. Read-only."""
        case = self._case(case_id)
        client = self.store.get_client(case["client_id"]) or {}

        def advisor(advisor_id: str | None) -> dict[str, Any] | None:
            found = self.store.get_advisor(advisor_id) if advisor_id else None
            return {"advisor_id": advisor_id, "display_name": found["display_name"]} if found else None

        case_account = (case.get("account_context") or {}).get("account_id")
        accounts, events = [], []
        for a in self.store.accounts_for_client(case["client_id"]):
            accounts.append({"account_id": a["account_id"], "label": a.get("label"), "familiar_label": a.get("familiar_label"),
                             "masked_identifier": a.get("masked_identifier"), "balance": a.get("balance"),
                             "balance_as_of": a.get("balance_as_of"), "is_case_account": a["account_id"] == case_account})
            for e in self.store.events_for_account(a["account_id"]):
                events.append({"date": e["date"], "type": e["type"], "summary": e.get("summary") or e.get("description") or "",
                               "account_label": a.get("label"), "masked_identifier": a.get("masked_identifier"), "source_id": e["source_id"]})
        others = [self.summary(c) for c in self.store.list_cases() if c["client_id"] == case["client_id"] and c["case_id"] != case_id]
        return {
            "case_id": case_id,
            "client": {k: client.get(k) for k in ("client_id", "display_name", "preferred_contact_channel", "meeting_preference", "state")},
            "usual_advisor": advisor(client.get("existing_advisor_id") or case.get("existing_advisor_id")),
            "assigned_advisor": advisor(case["routing"].get("assigned_advisor_id")),
            "accounts": accounts,
            "recent_events": sorted(events, key=lambda e: e["date"], reverse=True)[:8],
            "other_cases": others,
        }

    def reply_draft(self, case_id: str, instruction: str | None = None, ai_mode: str = "mock") -> dict[str, Any]:
        """Drafter + compliance-reviewer loop for a client message. Never mutates the case."""
        facts = self._agent_facts(self._case(case_id))
        instruction = (instruction or "").strip() or None
        from backend.aws import advisor_agents as aa
        result, note = self._run_agent(
            ai_mode,
            lambda: run_reply_workflow(facts, instruction, aa.draft_reply, aa.compliance_review),
            lambda: run_reply_workflow(facts, instruction, aa.stub_draft_reply, aa.stub_compliance_review), "agents")
        self._verdicts[(case_id, result["draft"].strip())] = result["review"]["verdict"]
        return {"case_id": case_id, "ai_mode": ai_mode, "note": note, **result}

    def compliance_review(self, case_id: str, draft: str | None = None, ai_mode: str = "mock") -> dict[str, Any]:
        """Compliance reviewer on the case record and, if given, a draft. Never mutates the case."""
        facts = self._agent_facts(self._case(case_id))
        draft = (draft or "").strip() or None
        from backend.aws import advisor_agents as aa
        result, note = self._run_agent(ai_mode, lambda: aa.compliance_review(facts, draft),
                                       lambda: aa.stub_compliance_review(facts, draft), "review")
        if draft:
            self._verdicts[(case_id, draft)] = result["verdict"]
        return {"case_id": case_id, "ai_mode": ai_mode, "note": note, **result}

    def _message_verdict(self, case_id: str, text: str, ai_mode: str) -> str:
        """The reviewer's verdict on exactly this text: the one already given, or a fresh review."""
        return self._verdicts.get((case_id, text)) or self.compliance_review(case_id, text, ai_mode)["verdict"]

    _ACTIONS = {
        "claim": "advisor_claimed",
        "note": "advisor_note",
        "clarify": "clarification_requested",
        "schedule": "meeting_scheduled",
        "resolve": "request_resolved",
        "approve": "action_approved",
        "escalate": "escalated_to_security",
    }

    def action(self, case_id: str, action: str, text: str | None = None, compliance: dict[str, Any] | None = None,
               ai_mode: str = "mock") -> dict[str, Any]:
        """Record an advisor action as a history event. 'clarify' moves the case to
        needs_client_followup; others keep the status and are derived from history.
        A 'clarify' message is checked by the compliance reviewer here, whatever the browser
        claims: a flagged message is refused unless ``compliance.override`` is set, and the
        verdict and any override are recorded on the event."""
        event_name = self._ACTIONS.get(action)
        if not event_name:
            raise ApiError(400, "INVALID_ACTION", f"Unknown advisor action {action!r}.")
        if action in ("note", "clarify", "resolve") and not (text or "").strip():
            raise ApiError(400, "MISSING_TEXT", f"The '{action}' action needs text.")
        if action == "escalate" and "fraud_or_security" not in self._case(case_id).get("categories", []):
            raise ApiError(400, "NOT_A_SECURITY_CASE", "Only security cases go to the security specialist team.")
        reviewed = None
        if action == "clarify":
            verdict = self._message_verdict(case_id, text.strip(), ai_mode)  # may call the model; outside the lock
            override = verdict == "needs_changes" and bool((compliance or {}).get("override"))
            if verdict == "needs_changes" and not override:
                raise ApiError(409, "COMPLIANCE_REVIEW_FAILED", "The compliance reviewer flagged this message. Revise it, or send it with an override.")
            reviewed = {"verdict": verdict, "override": override}
        with self.store.lock:
            case = self._case(case_id)
            now = now_iso()
            details: dict[str, Any] = {"by": "advisor-demo"}
            if text:
                details["text"] = text.strip()
            if reviewed:
                details["compliance"] = reviewed
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
