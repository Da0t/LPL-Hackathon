"""Deterministic rules: authorization boundary, proposal-vs-selection, validation of adapter output, failure paths."""

from __future__ import annotations

import time

from tests.backend.conftest import CLIENT, ROTH_THING, STAFF, confirm, make_client_with_adapter, start, submit_roth_thing_case, turn

# --------------------------------------------------------------- roles


def test_staff_endpoints_require_staff_role(client):
    case_id = submit_roth_thing_case(client)
    for method, path, payload in (
        ("get", "/staff/cases", None),
        ("get", f"/staff/cases/{case_id}", None),
        ("get", f"/staff/cases/{case_id}/candidates", None),
        ("post", f"/staff/cases/{case_id}/assign", {"advisor_id": "ADV-01", "staff_reason": "x"}),
        ("post", "/demo/reset", None),
    ):
        response = getattr(client, method)(path, json=payload) if payload else getattr(client, method)(path)
        assert response.status_code == 403, path
        assert response.json()["error_code"] == "forbidden"
        as_client = getattr(client, method)(path, json=payload, headers=CLIENT) if payload else getattr(client, method)(path, headers=CLIENT)
        assert as_client.status_code == 403, path


def test_intake_endpoints_reject_staff_role(client):
    response = client.post("/intake/start", json={"client_id": "CLIENT-017"}, headers=STAFF)
    assert response.status_code == 403


def test_role_query_param_is_accepted_for_browser_checks(client):
    submit_roth_thing_case(client)
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
    response = client.post("/intake/start", json={"client_id": "CLIENT-999"}, headers=CLIENT)
    assert response.status_code == 404
    assert response.json()["error_code"] == "client_not_found"


def test_client_cannot_confirm_another_clients_account(client):
    sid = start(client, "CLIENT-017")
    turn(client, sid, ROTH_THING)
    body = confirm(client, sid, "Money from my Roth IRA", "ACCT-211", expect=403)
    assert body["error_code"] == "account_not_authorized"
    # Draft preserved: the session can still be confirmed correctly.
    confirm(client, sid, "Money from my rollover IRA", "ACCT-201")


def test_adapter_cannot_see_other_clients_accounts(tmp_path):
    seen = {}

    def intake(client_id, transcript, selected_option_id, tools):
        seen["other"] = tools["get_relevant_accounts"]("CLIENT-022", transcript)
        seen["mine"] = tools.get_relevant_accounts(client_id, transcript)
        seen["history_other"] = tools["get_relevant_account_history"]("ACCT-211")
        return {"suggestions": [{"id": "opt-1", "label": "Your Roth IRA", "account_id": "ACCT-211"}], "selected_account_id": "ACCT-211", "question": "Is it this one?"}

    def triage(confirmed_request, tools):
        return {"categories": ["account_service"], "staff_summary": "s"}

    with make_client_with_adapter(tmp_path, intake, triage) as client:
        sid = start(client, "CLIENT-017")
        body = turn(client, sid, "my roth")
        assert seen["other"]["error"] == "not_authorized" and seen["other"]["accounts"] == []
        assert {a["account_id"] for a in seen["mine"]["accounts"]} == {"ACCT-201", "ACCT-202", "ACCT-203"}
        assert all("balance" not in a for a in seen["mine"]["accounts"]), "balances never reach the model"
        assert seen["history_other"]["error"] == "not_authorized"
        # The adapter's unauthorized account references are stripped, not trusted.
        assert body["suggestions"][0]["account_id"] is None
        assert body["candidate_account_id"] is None
        assert body["selected_account_id"] is None


# ------------------------------------------------ proposals vs choices


def test_model_selection_is_only_a_candidate_until_client_chooses(tmp_path):
    def intake(client_id, transcript, selected_option_id, tools):
        return {"suggestions": [{"id": "opt-1", "label": "Rollover IRA", "account_id": "ACCT-201"}], "selected_account_id": "ACCT-201", "question": "This one?", "candidate_intent": "discuss_possible_withdrawal"}

    def triage(confirmed_request, tools):
        return {"categories": ["withdrawal_or_distribution"], "staff_summary": "s"}

    with make_client_with_adapter(tmp_path, intake, triage) as client:
        sid = start(client, "CLIENT-017")
        first = turn(client, sid, "the old job account")
        assert first["selected_account_id"] is None
        assert first["candidate_account_id"] == "ACCT-201"
        second = turn(client, sid, option="opt-1")
        assert second["selected_account_id"] == "ACCT-201"


def test_amount_is_only_confirmed_on_review_and_compared_with_words(client):
    sid = start(client, "CLIENT-017")
    turn(client, sid, ROTH_THING)
    without_amount = confirm(client, sid, "Talk about my rollover IRA", "ACCT-201")
    case = client.get(f"/staff/cases/{without_amount['case_id']}", headers=STAFF).json()
    assert case["amount_requested"] is None, "the $6,000 in the words is never inferred into the case"
    assert any("amount" in q.lower() for q in case["unresolved_questions"])

    sid2 = start(client, "CLIENT-017")
    turn(client, sid2, ROTH_THING)
    changed = confirm(client, sid2, "Talk about my rollover IRA", "ACCT-201", 7500)
    case2 = client.get(f"/staff/cases/{changed['case_id']}", headers=STAFF).json()
    assert case2["amount_requested"] == 7500
    assert "amount_not_in_transcript" in case2["flags"]


def test_account_chosen_outside_suggestions_is_recorded_as_client_selected(client):
    sid = start(client, "CLIENT-017")
    turn(client, sid, ROTH_THING)
    result = confirm(client, sid, "Actually it is my joint account", "ACCT-202")
    case = client.get(f"/staff/cases/{result['case_id']}", headers=STAFF).json()
    assert case["account_match_status"] == "client_selected"
    assert "account_selected_outside_suggestions" in case["flags"]
    assert case["account_context"]["account_type"] == "joint_brokerage"


def test_invalid_option_and_empty_turn_are_rejected(client):
    sid = start(client)
    empty = client.post(f"/intake/{sid}/turn", json={"text": "", "input_mode": "text"}, headers=CLIENT)
    assert empty.status_code == 400 and empty.json()["error_code"] == "empty_turn"
    turn(client, sid, ROTH_THING)
    bad = client.post(f"/intake/{sid}/turn", json={"text": "", "input_mode": "text", "selected_option_id": "opt-99"}, headers=CLIENT)
    assert bad.status_code == 400 and bad.json()["error_code"] == "invalid_option"
    assert "none_of_these" in bad.json()["details"]["valid_option_ids"]


def test_confirm_requires_a_turn_and_only_once(client):
    sid = start(client)
    body = confirm(client, sid, "Anything", expect=409)
    assert body["error_code"] == "nothing_to_confirm"
    turn(client, sid, ROTH_THING)
    first = confirm(client, sid, "Talk about my rollover IRA", "ACCT-201")
    again = confirm(client, sid, "Talk about my rollover IRA", "ACCT-201", expect=409)
    assert again["error_code"] == "session_already_submitted"
    assert again["details"]["case_id"] == first["case_id"]
    later_turn = client.post(f"/intake/{sid}/turn", json={"text": "more"}, headers=CLIENT)
    assert later_turn.status_code == 409


def test_editing_transcript_replaces_words_and_records_modes(client):
    sid = start(client)
    turn(client, sid, "I need money", mode="voice")
    body = turn(client, sid, "I need money from my rollover IRA for a roof repair", mode="typed")
    assert body["transcript"].endswith("roof repair")
    result = confirm(client, sid, body["proposed_plain_language_request"] or "Rollover IRA money", "ACCT-201")
    case = client.get(f"/staff/cases/{result['case_id']}", headers=STAFF).json()
    assert case["input_mode"] == "mixed"
    assert case["original_words"].endswith("roof repair")


# ---------------------------------------------------- failure paths


def test_model_error_preserves_draft_and_explains(tmp_path):
    calls = {"n": 0}

    def intake(client_id, transcript, selected_option_id, tools):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("bedrock throttled")
        return {"suggestions": [{"id": "opt-1", "label": "Rollover IRA", "account_id": "ACCT-201"}], "question": "This one?"}

    def triage(confirmed_request, tools):
        return {"categories": ["account_service"], "staff_summary": "s"}

    with make_client_with_adapter(tmp_path, intake, triage) as client:
        sid = start(client)
        first = turn(client, sid, "old job money")
        failed = turn(client, sid, "old job money, the retirement one")
        assert failed["degraded"] is True
        assert failed["status"] == "needs_clarification"
        assert failed["message"] and "Talk to a person" in failed["message"]
        assert failed["transcript"] == "old job money, the retirement one", "words preserved"
        assert failed["suggestions"] == first["suggestions"], "previous options still usable"
        assert failed["question"] == first["question"]
        # The client can still continue, select the preserved option, and confirm.
        third = turn(client, sid, option="opt-1")
        assert third["selected_account_id"] == "ACCT-201"
        confirm(client, sid, "Money from my rollover IRA", "ACCT-201")


def test_model_timeout_is_a_preserved_draft(tmp_path):
    def intake(client_id, transcript, selected_option_id, tools):
        time.sleep(5)
        return {}

    def triage(confirmed_request, tools):
        return {}

    with make_client_with_adapter(tmp_path, intake, triage) as client:
        sid = start(client)
        body = turn(client, sid, "hello")
        assert body["degraded"] is True and body["status"] == "needs_clarification"
        assert body["transcript"] == "hello"


def test_triage_failure_still_creates_reviewable_case(tmp_path):
    def intake(client_id, transcript, selected_option_id, tools):
        return {"suggestions": [], "question": None, "candidate_intent": "discuss_possible_withdrawal"}

    def triage(confirmed_request, tools):
        raise TimeoutError("model down")

    with make_client_with_adapter(tmp_path, intake, triage) as client:
        sid = start(client)
        turn(client, sid, ROTH_THING)
        result = confirm(client, sid, "Money from my rollover IRA", "ACCT-201", 6000)
        case = client.get(f"/staff/cases/{result['case_id']}", headers=STAFF).json()
        assert case["triage"]["status"] == "failed"
        assert "triage_unavailable" in case["flags"]
        assert case["categories"] == ["withdrawal_or_distribution", "retirement_income"], "deterministic fallback from intent"
        assert "staff review required" in case["staff_summary"]
        assert case["account_context"]["balance"] == 84000, "account facts still come from records"
        assert case["routing"]["recommended_advisor_ids"], "ranking is deterministic and still works"


# --------------------------------------------- validating model output


def test_model_output_is_sanitized(tmp_path):
    def intake(client_id, transcript, selected_option_id, tools):
        return {
            "suggestions": [{"id": f"opt-{i}", "label": f"Option {i}", "account_id": "ACCT-201"} for i in range(6)],
            "question": "Which?",
            "definitions": [{"term": "Roth IRA", "plain": "the model made this up"}, {"term": "Hedge fund", "plain": "nope"}],
            "selected_account_id": "ACCT-211",
        }

    def triage(confirmed_request, tools):
        return {
            "categories": ["withdrawal_or_distribution", "crypto_trading", "Retirement Income"],
            "flags": ["Client Term Did Not Match Account Type"],
            "account_context": {"balance": 1_000_000, "balance_as_of": "2030-01-01"},
            "amount_requested": 999_999,
            "recommended_advisor_ids": ["ADV-01", "ADV-404"],
            "recommended_destination": "mars_colony",
            "staff_summary": "Client requests discussion of a distribution.",
            "unresolved_questions": ["Timing"],
        }

    with make_client_with_adapter(tmp_path, intake, triage) as client:
        sid = start(client)
        body = turn(client, sid, "roth from my old job")
        assert len(body["suggestions"]) == 3
        assert body["candidate_account_id"] is None, "unauthorized proposal dropped"
        assert [d["term"] for d in body["definitions"]] == ["Roth IRA"]
        assert "made this up" not in body["definitions"][0]["plain"], "approved glossary text wins"
        result = confirm(client, sid, "Money from my rollover IRA", "ACCT-201")
        case = client.get(f"/staff/cases/{result['case_id']}", headers=STAFF).json()
        assert case["categories"] == ["withdrawal_or_distribution", "retirement_income"]
        assert case["account_context"]["balance"] == 84000 and case["account_context"]["balance_as_of"] == "2026-10-01"
        assert case["amount_requested"] is None
        assert case["routing"]["model_recommended_advisor_ids"] == ["ADV-01"]
        assert case["routing"]["destination"] == "retirement_advisor_review"
        assert "client_term_did_not_match_account_type" in case["flags"]
        assert any("crypto_trading" in n for n in case["triage"]["validation_notes"])


def test_assignment_rules(client):
    case_id = submit_roth_thing_case(client)
    inactive = client.post(f"/staff/cases/{case_id}/assign", json={"advisor_id": "ADV-07", "staff_reason": "x"}, headers=STAFF)
    assert inactive.status_code == 409 and inactive.json()["error_code"] == "advisor_not_active"
    unknown = client.post(f"/staff/cases/{case_id}/assign", json={"advisor_id": "ADV-99", "staff_reason": "x"}, headers=STAFF)
    assert unknown.status_code == 404
    blank_reason = client.post(f"/staff/cases/{case_id}/assign", json={"advisor_id": "ADV-01", "staff_reason": "   "}, headers=STAFF)
    assert blank_reason.status_code == 400
    override = client.post(f"/staff/cases/{case_id}/assign", json={"advisor_id": "ADV-02", "staff_reason": "Client moved to Texas."}, headers=STAFF).json()
    assert "staff_overrode_recommendation" in override["flags"]
    again = client.post(f"/staff/cases/{case_id}/assign", json={"advisor_id": "ADV-01", "staff_reason": "Correction."}, headers=STAFF).json()
    assert again["assigned_advisor_id"] == "ADV-01"
    case = client.get(f"/staff/cases/{case_id}", headers=STAFF).json()
    assert case["history"][-1]["event"] == "reassigned"
    assert case["routing"]["staff_decision"]["advisor_id"] == "ADV-01"


def test_queue_filters(client):
    case_id = submit_roth_thing_case(client)
    assert client.get("/staff/cases?status=submitted", headers=STAFF).json()["cases"][0]["case_id"] == case_id
    assert client.get("/staff/cases?status=assigned", headers=STAFF).json()["cases"] == []
    assert client.get("/staff/cases?category=withdrawal_or_distribution", headers=STAFF).json()["cases"]
    assert client.get("/staff/cases?category=fraud_or_security", headers=STAFF).json()["cases"] == []
