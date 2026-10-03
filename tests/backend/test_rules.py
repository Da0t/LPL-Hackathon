"""Deterministic rules: authorization boundary, proposal-vs-selection, validation of adapter output, failure paths."""

from __future__ import annotations

import time

from tests.backend.conftest import CLIENT, ROTH_THING, STAFF, client_headers, confirm, make_client_with_adapter, start, submit_roth_thing_case, turn

# --------------------------------------------------------------- roles


def test_staff_endpoints_require_staff_role(client):
    case_id = submit_roth_thing_case(client)
    for method, path, payload in (
        ("get", "/staff/cases", None),
        ("get", f"/staff/cases/{case_id}", None),
        ("get", f"/staff/cases/{case_id}/candidates", None),
        ("post", f"/staff/cases/{case_id}/assign", {"advisor_id": "ADV-03", "staff_reason": "x"}),
        ("post", "/demo/reset", None),
    ):
        for headers in ({}, CLIENT):
            response = getattr(client, method)(path, json=payload, headers=headers) if payload else getattr(client, method)(path, headers=headers)
            assert response.status_code == 403, path
            assert response.json()["error_code"] == "WRONG_DEMO_ROLE"


def test_intake_endpoints_reject_staff_role(client):
    response = client.post("/intake/start", json={"client_id": "CLIENT-017"}, headers=STAFF)
    assert response.status_code == 403 and response.json()["error_code"] == "WRONG_DEMO_ROLE"


def test_role_query_param_is_accepted_for_browser_checks(client):
    assert client.get("/staff/cases?demo_role=staff").status_code == 200


def test_default_role_can_be_staff_for_ui_development(tmp_path):
    from fastapi.testclient import TestClient

    from backend.main import create_app
    from tests.backend.conftest import make_settings

    with TestClient(create_app(make_settings(tmp_path, default_demo_role="staff"))) as client:
        assert client.get("/staff/cases").status_code == 200
        assert client.post("/intake/start", json={"client_id": "CLIENT-017"}).status_code == 403
        assert client.post("/intake/start", json={"client_id": "CLIENT-017"}, headers=CLIENT).status_code == 200


# ---------------------------------------------------- client scoping


def test_unknown_client_cannot_start(client):
    response = client.post("/intake/start", json={"client_id": "CLIENT-999"}, headers=client_headers("CLIENT-999"))
    assert response.status_code == 404 and response.json()["error_code"] == "CLIENT_NOT_FOUND"


def test_demo_client_header_must_match_the_session(client):
    wrong = client.post("/intake/start", json={"client_id": "CLIENT-017"}, headers=client_headers("CLIENT-022"))
    assert wrong.status_code == 403 and wrong.json()["error_code"] == "WRONG_DEMO_CLIENT"
    sid = start(client, "CLIENT-017")
    hijack = client.post(f"/intake/{sid}/turn", json={"text": "hello"}, headers=client_headers("CLIENT-022"))
    assert hijack.status_code == 403 and hijack.json()["error_code"] == "WRONG_DEMO_CLIENT"
    hijack_confirm = client.post(f"/intake/{sid}/confirm", json={"confirmed_plain_language_request": "x"}, headers=client_headers("CLIENT-022"))
    assert hijack_confirm.status_code == 403
    # Header optional for curl-style checks; role still required.
    assert client.post(f"/intake/{sid}/turn", json={"text": "hello"}, headers={"X-Demo-Role": "client"}).status_code == 200


def test_client_cannot_confirm_another_clients_account(client):
    sid = start(client, "CLIENT-017")
    turn(client, sid, ROTH_THING)
    body = confirm(client, sid, "Money from my Roth IRA", "ACCT-301", expect=403)
    assert body["error_code"] == "ACCOUNT_MISMATCH"
    confirm(client, sid, "Money from my rollover IRA", "ACCT-201")  # draft preserved


def test_tools_match_agent1_seam_and_hide_balances(tmp_path):
    """Agent 1's adapter calls the callbacks with keyword arguments and iterates list results.
    Intake sees only accounts + glossary; history and the advisor directory arrive at triage."""
    seen = {}

    def intake(client_id, transcript, selected_option_id, tools):
        seen["intake_tools"] = sorted(tools.keys())
        seen["mine"] = tools.get_relevant_accounts(client_id=client_id, phrase=transcript)
        seen["other"] = tools["get_relevant_accounts"](client_id="CLIENT-022", phrase=transcript)
        seen["positional_phrase"] = tools.get_relevant_accounts("my roth")
        seen["definition"] = tools.get_approved_definition(term="rollover IRA")
        return {"suggestions": [{"id": "ACCT-301", "label": "Roth retirement account", "account_id": "ACCT-301"}], "selected_account_id": "ACCT-301", "question": "Is it this one?", "definitions": [], "candidate_intent": "account_service", "uncertainty": None}

    def triage(confirmed_request, tools):
        seen["confirmed_request"] = confirmed_request
        seen["history_mine"] = tools.get_relevant_account_history(account_id="ACCT-201")
        seen["history_other"] = tools.get_relevant_account_history(account_id="ACCT-301")
        seen["advisors"] = tools.search_advisor_directory(categories=["withdrawal_or_distribution"], preferences={})
        seen["security"] = tools.search_advisor_directory(categories=["fraud_or_security"], preferences={})
        return {"categories": ["account_service"], "staff_summary": "s", "client_summary": "c", "intent": "x", "unresolved_questions": [], "flags": [], "recommended_advisor_ids": [], "routing_hint": None}

    with make_client_with_adapter(tmp_path, intake, triage) as client:
        sid = start(client, "CLIENT-017")
        body = turn(client, sid, "my roth from my old job")
        assert "get_relevant_account_history" not in seen["intake_tools"] and "search_advisor_directory" not in seen["intake_tools"]
        assert {"get_relevant_accounts", "get_approved_definition"} <= set(seen["intake_tools"])
        assert isinstance(seen["mine"], list) and [a["account_id"] for a in seen["mine"]] == ["ACCT-201", "ACCT-202"]
        assert {"account_id", "account_type", "familiar_label", "masked_identifier"} <= set(seen["mine"][0])
        assert all("balance" not in a and "balance_as_of" not in a for a in seen["mine"]), "balances never reach the model"
        assert seen["other"] == []
        assert [a["account_id"] for a in seen["positional_phrase"]] == ["ACCT-201", "ACCT-202"]
        assert seen["definition"]["term"] == "rollover IRA" and set(seen["definition"]) >= {"term", "plain"}
        # The adapter's unauthorized account references are stripped, not trusted.
        assert body["suggestions"][0]["account_id"] is None and body["candidate_account_id"] is None and body["selected_account_id"] is None
        confirm(client, sid, "Money from my rollover IRA", "ACCT-201")
        assert isinstance(seen["history_mine"], list) and {e["source_id"] for e in seen["history_mine"]} == {"EVENT-09", "EVENT-14"}
        assert {"type", "date", "source_id", "summary"} <= set(seen["history_mine"][0])
        assert seen["history_other"] == []
        assert isinstance(seen["advisors"], list) and {"advisor_id", "display_name", "specialties", "available"} <= set(seen["advisors"][0])
        assert seen["security"] == []
        cr = seen["confirmed_request"]
        assert cr["selected_account_id"] == "ACCT-201" and cr["original_words"] == "my roth from my old job"
        assert {"confirmed_plain_language_request", "original_words", "candidate_intent", "amount_requested"} <= set(cr)
        assert "balance" not in str(cr)


# ------------------------------------------------ proposals vs choices


def test_model_selection_is_only_a_candidate_until_client_chooses(tmp_path):
    def intake(client_id, transcript, selected_option_id, tools):
        return {"suggestions": [{"id": "ACCT-201", "label": "Retirement account from former employer", "account_id": "ACCT-201"}], "selected_account_id": "ACCT-201", "question": "This one?", "candidate_intent": "discuss_possible_withdrawal"}

    def triage(confirmed_request, tools):
        return {"categories": ["withdrawal_or_distribution"], "staff_summary": "s"}

    with make_client_with_adapter(tmp_path, intake, triage) as client:
        sid = start(client, "CLIENT-017")
        first = turn(client, sid, "the old job account")
        assert first["selected_account_id"] is None and first["candidate_account_id"] == "ACCT-201"
        second = turn(client, sid, option="ACCT-201")
        assert second["selected_account_id"] == "ACCT-201"


def test_amount_is_only_confirmed_on_review_and_compared_with_words(client):
    sid = start(client, "CLIENT-017")
    turn(client, sid, ROTH_THING)
    without_amount = confirm(client, sid, "Talk about my rollover IRA", "ACCT-201")
    case = client.get(f"/staff/cases/{without_amount['case_id']}", headers=STAFF).json()
    assert case["amount_requested"] is None and case["currency"] is None, "the $6,000 in the words is never inferred into the case"
    assert any("amount" in q.lower() for q in case["unresolved_questions"])

    sid2 = start(client, "CLIENT-017")
    turn(client, sid2, ROTH_THING)
    changed = confirm(client, sid2, "Talk about my rollover IRA", "ACCT-201", 7500)
    case2 = client.get(f"/staff/cases/{changed['case_id']}", headers=STAFF).json()
    assert case2["amount_requested"] == 7500 and "amount_not_in_transcript" in case2["flags"]


def test_account_chosen_outside_suggestions_is_recorded_as_client_selected(client):
    sid = start(client, "CLIENT-017")
    turn(client, sid, ROTH_THING)
    result = confirm(client, sid, "Actually it is my everyday investments account", "ACCT-202")
    case = client.get(f"/staff/cases/{result['case_id']}", headers=STAFF).json()
    assert case["account_match_status"] == "client_selected"
    assert "account_selected_outside_suggestions" in case["flags"]
    assert case["account_context"]["account_type"] == "brokerage"
    assert any("Roth IRA" in c["statement"] for c in case["conflicts"])


def test_invalid_option_and_empty_turn_are_rejected(client):
    sid = start(client)
    empty = client.post(f"/intake/{sid}/turn", json={"text": "", "input_mode": "text"}, headers=CLIENT)
    assert empty.status_code == 400 and empty.json()["error_code"] == "INVALID_TURN"
    turn(client, sid, ROTH_THING)
    bad = client.post(f"/intake/{sid}/turn", json={"text": "", "input_mode": "text", "selected_option_id": "opt-99"}, headers=CLIENT)
    assert bad.status_code == 400 and bad.json()["error_code"] == "INVALID_OPTION"
    assert "none_of_these" in bad.json()["details"]["valid_option_ids"]


def test_confirm_requires_a_turn_and_only_once(client):
    sid = start(client)
    assert confirm(client, sid, "Anything", expect=409)["error_code"] == "NOTHING_TO_CONFIRM"
    turn(client, sid, ROTH_THING)
    first = confirm(client, sid, "Talk about my rollover IRA", "ACCT-201")
    again = confirm(client, sid, "Talk about my rollover IRA", "ACCT-201", expect=409)
    assert again["error_code"] == "SESSION_ALREADY_SUBMITTED" and again["details"]["case_id"] == first["case_id"]
    assert client.post(f"/intake/{sid}/turn", json={"text": "more"}, headers=CLIENT).status_code == 409
    blank = client.post(f"/intake/{start(client)}/confirm", json={"confirmed_plain_language_request": "   "}, headers=CLIENT)
    assert blank.status_code in (400, 409, 422)


def test_editing_transcript_replaces_words_and_records_modes(client):
    sid = start(client)
    turn(client, sid, "I need money", mode="voice")
    body = turn(client, sid, "I need money from my rollover IRA for a roof repair", mode="typed")
    assert body["transcript"].endswith("roof repair")
    result = confirm(client, sid, body["proposed_plain_language_request"] or "Rollover IRA money", "ACCT-201")
    case = client.get(f"/staff/cases/{result['case_id']}", headers=STAFF).json()
    assert case["input_mode"] == "mixed" and case["original_words"].endswith("roof repair")


# ---------------------------------------------------- failure paths


def test_model_error_preserves_draft_and_surfaces_adapter_message(tmp_path):
    class BedrockAdapterError(Exception):  # mirrors Agent 1's exception shape
        def __init__(self, code, message):
            super().__init__(message)
            self.code, self.message = code, message

    calls = {"n": 0}

    def intake(client_id, transcript, selected_option_id, tools):
        calls["n"] += 1
        if calls["n"] == 2:
            raise BedrockAdapterError("BEDROCK_CALL_FAILED", "The assistant is temporarily unavailable. You can keep typing or ask to talk to a person.")
        return {"suggestions": [{"id": "ACCT-201", "label": "Retirement account from former employer", "account_id": "ACCT-201"}], "question": "This one?"}

    def triage(confirmed_request, tools):
        return {"categories": ["account_service"], "staff_summary": "s"}

    with make_client_with_adapter(tmp_path, intake, triage) as client:
        sid = start(client)
        first = turn(client, sid, "old job money")
        failed = turn(client, sid, "old job money, the retirement one")
        assert failed["degraded"] is True and failed["status"] == "needs_clarification"
        assert failed["message"] == "The assistant is temporarily unavailable. You can keep typing or ask to talk to a person."
        assert failed["transcript"] == "old job money, the retirement one", "words preserved"
        assert failed["suggestions"] == first["suggestions"] and failed["question"] == first["question"], "previous options still usable"
        third = turn(client, sid, option="ACCT-201")
        assert third["selected_account_id"] == "ACCT-201"
        confirm(client, sid, "Money from my rollover IRA", "ACCT-201")


def test_model_timeout_is_a_preserved_draft(tmp_path):
    def intake(client_id, transcript, selected_option_id, tools):
        time.sleep(5)
        return {}

    with make_client_with_adapter(tmp_path, intake, lambda cr, tools: {}) as client:
        sid = start(client)
        body = turn(client, sid, "hello")
        assert body["degraded"] is True and body["status"] == "needs_clarification" and body["transcript"] == "hello"
        assert "Talk to a person" in body["message"]


def test_triage_failure_still_creates_reviewable_case(tmp_path):
    def intake(client_id, transcript, selected_option_id, tools):
        return {"suggestions": [], "question": None, "candidate_intent": "discuss_possible_withdrawal"}

    def triage(confirmed_request, tools):
        raise TimeoutError("model down")

    with make_client_with_adapter(tmp_path, intake, triage) as client:
        sid = start(client)
        turn(client, sid, ROTH_THING)
        result = confirm(client, sid, "Money from my rollover IRA", "ACCT-201", 6000)
        assert result["client_summary"] == "Your request has been sent for staff review."
        case = client.get(f"/staff/cases/{result['case_id']}", headers=STAFF).json()
        assert case["triage"]["status"] == "failed" and "triage_unavailable" in case["flags"]
        assert case["categories"] == ["withdrawal_or_distribution", "retirement_income"], "deterministic fallback from intent"
        assert "staff review required" in case["staff_summary"]
        assert case["account_context"]["balance"] == 84000 and case["routing"]["recommended_advisor_ids"]


# --------------------------------------------- validating model output


def test_model_output_is_sanitized(tmp_path):
    def intake(client_id, transcript, selected_option_id, tools):
        return {
            "suggestions": [{"id": f"opt-{i}", "label": f"Option {i}", "account_id": "ACCT-201"} for i in range(6)],
            "question": "Which?",
            "definitions": [{"term": "Roth IRA", "plain": "the model made this up"}, {"term": "Hedge fund", "plain": "nope"}],
            "selected_account_id": "ACCT-301",
        }

    def triage(confirmed_request, tools):
        return {
            "categories": "withdrawal_or_distribution, crypto_trading, Retirement Income",
            "flags": ["Client Term Did Not Match Account Type"],
            "account_context": {"balance": 1_000_000, "balance_as_of": "2030-01-01"},
            "amount_requested": 999_999,
            "recommended_advisor_ids": ["ADV-03", "ADV-404"],
            "routing_hint": "mars_colony",
            "staff_summary": "Client requests discussion of a distribution.",
            "client_summary": "Thanks, we sent it along.",
            "unresolved_questions": ["Timing"],
        }

    with make_client_with_adapter(tmp_path, intake, triage) as client:
        sid = start(client)
        body = turn(client, sid, "roth from my old job")
        assert len(body["suggestions"]) == 3 and body["candidate_account_id"] is None
        assert [d["term"] for d in body["definitions"]] == ["Roth IRA"] and "made this up" not in body["definitions"][0]["plain"]
        result = confirm(client, sid, "Money from my rollover IRA", "ACCT-201")
        assert result["client_summary"] == "Thanks, we sent it along."
        case = client.get(f"/staff/cases/{result['case_id']}", headers=STAFF).json()
        assert case["categories"] == ["withdrawal_or_distribution", "retirement_income"]
        assert case["account_context"]["balance"] == 84000 and case["account_context"]["balance_as_of"] == "2026-10-01"
        assert case["amount_requested"] is None
        assert case["routing"]["model_recommended_advisor_ids"] == ["ADV-03"] and case["routing"]["model_routing_hint"] is None
        assert case["routing"]["destination"] == "retirement_advisor_review"
        assert "client_term_did_not_match_account_type" in case["flags"]
        assert any("crypto_trading" in n for n in case["triage"]["validation_notes"])


def test_agent1_routing_hint_vocabulary_is_accepted(tmp_path):
    def intake(client_id, transcript, selected_option_id, tools):
        return {"suggestions": [], "question": None, "candidate_intent": "review_account_access", "selected_account_id": None, "definitions": [], "uncertainty": None}

    def triage(confirmed_request, tools):
        return {"client_summary": "c", "staff_summary": "s", "intent": "review_account_access", "categories": ["fraud_or_security", "account_service"],
                "unresolved_questions": [], "flags": ["possible_unauthorized_access"], "recommended_advisor_ids": [], "routing_hint": "security_specialist_review"}

    with make_client_with_adapter(tmp_path, intake, triage) as client:
        sid = start(client, "CLIENT-022")
        turn(client, sid, "Please review my account", client_id="CLIENT-022")
        result = confirm(client, sid, "Please review my account", None, client_id="CLIENT-022")
        case = client.get(f"/staff/cases/{result['case_id']}", headers=STAFF).json()
        assert case["routing"]["destination"] == "security_specialist_review" and case["routing"]["model_routing_hint"] == "security_specialist_review"
        assert case["account_match_status"] == "not_needed"


def test_assignment_rules(client):
    case_id = submit_roth_thing_case(client)
    inactive = client.post(f"/staff/cases/{case_id}/assign", json={"advisor_id": "ADV-08", "staff_reason": "x"}, headers=STAFF)
    assert inactive.status_code == 409 and inactive.json()["error_code"] == "ADVISOR_NOT_ACTIVE"
    unknown = client.post(f"/staff/cases/{case_id}/assign", json={"advisor_id": "ADV-99", "staff_reason": "x"}, headers=STAFF)
    assert unknown.status_code == 404 and unknown.json()["error_code"] == "ADVISOR_NOT_FOUND"
    blank_reason = client.post(f"/staff/cases/{case_id}/assign", json={"advisor_id": "ADV-03", "staff_reason": "   "}, headers=STAFF)
    assert blank_reason.status_code == 400 and blank_reason.json()["error_code"] == "INVALID_ASSIGNMENT"
    override = client.post(f"/staff/cases/{case_id}/assign", json={"advisor_id": "ADV-01", "staff_reason": "Client moved to Texas."}, headers=STAFF).json()
    assert "staff_overrode_recommendation" in override["flags"]
    again = client.post(f"/staff/cases/{case_id}/assign", json={"advisor_id": "ADV-03", "staff_reason": "Correction."}, headers=STAFF).json()
    assert again["assigned_advisor_id"] == "ADV-03"
    case = client.get(f"/staff/cases/{case_id}", headers=STAFF).json()
    assert case["history"][-1]["event"] == "reassigned" and case["routing"]["staff_decision"] == "Correction."


def test_queue_filters(client):
    case_id = submit_roth_thing_case(client)
    assert client.get("/staff/cases?status=submitted", headers=STAFF).json()["cases"][0]["case_id"] == case_id
    assert client.get("/staff/cases?status=assigned", headers=STAFF).json()["cases"] == []
    assert {c["case_id"] for c in client.get("/staff/cases?category=fraud_or_security", headers=STAFF).json()["cases"]} == {"CASE-SEC-1"}


# ------------------------------------------------ fixes from the adversarial review


def test_model_cannot_shadow_reserved_option_ids(tmp_path):
    def intake(client_id, transcript, selected_option_id, tools):
        if selected_option_id == "talk_to_person":
            return {"suggestions": [], "question": None, "candidate_intent": "general_question"}
        return {"suggestions": [{"id": "talk_to_person", "label": "Retirement account from former employer", "account_id": "ACCT-201"},
                                {"id": "none_of_these", "label": "Everyday investments", "account_id": "ACCT-202"}], "question": "Which?"}

    with make_client_with_adapter(tmp_path, intake, lambda cr, tools: {"categories": ["other_or_unclear"], "staff_summary": "s"}) as client:
        sid = start(client)
        first = turn(client, sid, "help me")
        assert {s["id"] for s in first["suggestions"]}.isdisjoint({"talk_to_person", "none_of_these"}), "reserved ids are renamed"
        handoff = turn(client, sid, option="talk_to_person")
        assert handoff["selected_account_id"] is None and handoff["status"] == "ready_for_client_review"
        result = confirm(client, sid, handoff["proposed_plain_language_request"])
        assert "client_requested_human_help" in client.get(f"/staff/cases/{result['case_id']}", headers=STAFF).json()["flags"]


def test_non_dict_adapter_result_is_a_degraded_turn_not_a_finished_answer(tmp_path):
    answers = iter([None, "not json at all", {"suggestions": [], "question": None}])

    def intake(client_id, transcript, selected_option_id, tools):
        return next(answers)

    with make_client_with_adapter(tmp_path, intake, lambda cr, tools: {"categories": ["other_or_unclear"], "staff_summary": "s"}) as client:
        sid = start(client)
        for _ in range(2):
            body = turn(client, sid, "hello there")
            assert body["degraded"] is True and body["status"] == "needs_clarification"
        assert turn(client, sid, "hello there")["degraded"] is False


def test_dict_like_adapter_results_are_accepted(tmp_path):
    from dataclasses import asdict, dataclass

    @dataclass
    class IntakeResult:
        suggestions: list
        question: str | None
        candidate_intent: str

        def model_dump(self):
            return asdict(self)

    def intake(client_id, transcript, selected_option_id, tools):
        return IntakeResult(suggestions=[], question=None, candidate_intent="general_question")

    with make_client_with_adapter(tmp_path, intake, lambda cr, tools: '{"categories": ["account_service"], "staff_summary": "from json"}') as client:
        sid = start(client)
        body = turn(client, sid, "hello")
        assert body["degraded"] is False and body["status"] == "ready_for_client_review"
        result = confirm(client, sid, "hello")
        assert client.get(f"/staff/cases/{result['case_id']}", headers=STAFF).json()["staff_summary"] == "from json"


def test_model_flags_cannot_impersonate_backend_flags(tmp_path):
    def triage(confirmed_request, tools):
        return {"categories": ["account_service"], "staff_summary": "s",
                "flags": ["security_keywords_detected", "staff_overrode_recommendation", "client_term_did_not_match_account_type", "Needs Spanish Speaker"]}

    with make_client_with_adapter(tmp_path, lambda *a: {"suggestions": [], "question": None}, triage) as client:
        sid = start(client)
        turn(client, sid, "a question about my investments")
        case = client.get(f"/staff/cases/{confirm(client, sid, 'A question about my investments', 'ACCT-202')['case_id']}", headers=STAFF).json()
        assert "security_keywords_detected" not in case["flags"] and "staff_overrode_recommendation" not in case["flags"]
        assert "client_term_did_not_match_account_type" in case["flags"] and "model_needs_spanish_speaker" in case["flags"]
        assert any("backend-owned" in n for n in case["triage"]["validation_notes"])


def test_bad_request_bodies_never_become_500(client):
    form = client.post("/intake/start", data={"client_id": "CLIENT-017"}, headers=CLIENT)
    assert form.status_code in (400, 422) and form.json()["error_code"] in {"VALIDATION_ERROR", "INVALID_JSON"}
    text = client.post("/intake/start", content="client_id=CLIENT-017", headers={**CLIENT, "Content-Type": "text/plain"})
    assert text.status_code in (400, 422)
    sid = start(client)
    boolean = client.post(f"/intake/{sid}/confirm", json={"confirmed_plain_language_request": "x", "amount_requested": True}, headers=CLIENT)
    assert boolean.status_code == 422 and boolean.json()["error_code"] == "VALIDATION_ERROR"


def test_amount_strings_with_commas_are_accepted(client):
    sid = start(client)
    turn(client, sid, "I need 6,000 from my rollover IRA")
    result = confirm(client, sid, "Money from my rollover IRA", "ACCT-201", "6,000")
    case = client.get(f"/staff/cases/{result['case_id']}", headers=STAFF).json()
    assert case["amount_requested"] == 6000 and "amount_not_in_transcript" not in case["flags"]


def test_static_catch_all_does_not_swallow_api_paths(client):
    submit_roth_thing_case(client)
    redirected = client.get("/staff/cases/", headers=STAFF, follow_redirects=False)
    assert redirected.status_code == 307 and redirected.headers["location"] == "/staff/cases"
    assert client.get("/staff/cases/", headers=STAFF).status_code == 200
    typo = client.get("/staff/cases/CASE-1043/candidate", headers=STAFF)
    assert typo.status_code == 404 and "API route" in typo.json()["message"]
    assert client.get("/intake/start").status_code == 405
    assert client.get("/client/%00").status_code == 404 and client.get("/staff/a%00b").status_code == 404


def test_unclear_request_still_offers_general_candidates(client):
    sid = start(client, "CLIENT-017")  # Mara has no existing advisor
    turn(client, sid, "I am not sure what I need, can someone help me understand my situation?")
    result = confirm(client, sid, "I would like to talk with someone about my situation.")
    body = client.get(f"/staff/cases/{result['case_id']}/candidates", headers=STAFF).json()
    assert body["destination"] == "advisor_review"
    assert 1 <= len(body["candidates"]) <= 3 and all(c["available"] for c in body["candidates"])
    assert "General request" in body["candidates"][0]["reason"]


def test_typing_after_talk_to_person_resumes_clarification(client):
    sid = start(client, "CLIENT-017")
    turn(client, sid, "I need help with something")
    assert turn(client, sid, option="talk_to_person")["status"] == "ready_for_client_review"
    resumed = turn(client, sid, "Actually, I want to take money out of my Roth account from my old job")
    assert resumed["status"] == "needs_clarification" and resumed["question"]
    result = confirm(client, sid, "Money from my rollover IRA", "ACCT-201")
    assert "client_requested_human_help" not in client.get(f"/staff/cases/{result['case_id']}", headers=STAFF).json()["flags"]


def test_changing_words_to_a_different_account_type_demotes_the_selection(client):
    sid = start(client, "CLIENT-017")
    first = turn(client, sid, ROTH_THING)
    picked = turn(client, sid, option=next(s["id"] for s in first["suggestions"] if s["account_id"] == "ACCT-201"))
    assert picked["selected_account_id"] == "ACCT-201"
    changed = turn(client, sid, "Actually I mean my brokerage account, the everyday investments one")
    assert changed["selected_account_id"] is None, "the pick becomes a proposal again when the words contradict it"
    assert "ACCT-202" in {s["account_id"] for s in changed["suggestions"]} or changed["candidate_account_id"] in {"ACCT-201", "ACCT-202"}
