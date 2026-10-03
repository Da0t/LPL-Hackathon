"""End-to-end synthetic scenarios: ambiguous IRA, clear request, beneficiary, specialist security routing."""

from __future__ import annotations

from tests.backend.conftest import BENEFICIARY, CLEAR_ROTH, ROTH_THING, SECURITY, STAFF, confirm, start, turn


def test_ambiguous_roth_thing_end_to_end(client):
    sid = start(client, "CLIENT-017")

    first = turn(client, sid, ROTH_THING, mode="voice")
    assert first["status"] == "needs_clarification"
    assert "Roth IRA" in first["question"] and "rollover" in first["question"].lower()
    assert first["selected_account_id"] is None, "a model suggestion must not be auto-selected"
    assert {s["account_id"] for s in first["suggestions"]} >= {"ACCT-201"}
    assert len(first["suggestions"]) <= 3
    terms = {d["term"] for d in first["definitions"]}
    assert "Rollover IRA" in terms
    assert "no Roth IRA" in first["uncertainty"]

    yes = next(s for s in first["suggestions"] if s["account_id"] == "ACCT-201")
    second = turn(client, sid, option=yes["id"])
    assert second["selected_account_id"] == "ACCT-201", "client choice sets the account"
    assert second["status"] == "needs_clarification"
    assert "taking money out" in second["question"].lower()

    third = turn(client, sid, option="opt-withdraw")
    assert third["status"] == "ready_for_client_review"
    assert third["question"] is None
    assert "$6,000" in third["proposed_plain_language_request"]
    assert "****4821" in third["proposed_plain_language_request"]

    result = confirm(client, sid, third["proposed_plain_language_request"], "ACCT-201", 6000)
    assert result["status"] == "submitted"
    case_id = result["case_id"]

    queue = client.get("/staff/cases", headers=STAFF).json()["cases"]
    row = next(c for c in queue if c["case_id"] == case_id)
    assert row["status"] == "submitted"
    assert "withdrawal_or_distribution" in row["categories"]
    assert "client_term_did_not_match_account_type" in row["flags"]

    case = client.get(f"/staff/cases/{case_id}", headers=STAFF).json()
    assert case["status"] == "staff_review", "opening the case moves it to staff review"
    assert case["original_words"] == ROTH_THING
    assert case["input_mode"] in {"voice", "mixed"}
    assert case["amount_requested"] == 6000
    assert case["selected_account_id"] == "ACCT-201"
    assert case["account_match_status"] == "client_confirmed"
    assert "retirement_income" in case["categories"]
    ctx = case["account_context"]
    assert ctx["account_type"] == "rollover_ira"
    assert ctx["masked_identifier"] == "****4821"
    assert ctx["balance"] == 84000 and ctx["balance_as_of"] == "2026-10-01"
    assert any(e["type"] == "rollover" and e["source_id"] == "EVENT-09" for e in ctx["relevant_events"])
    assert any("no Roth IRA" in c for c in ctx["conflicts"])
    assert any("Tax effects" in c for c in ctx["cautions"])
    assert ctx["source_id"] in ctx["sources"]
    assert "rollover IRA" in case["staff_summary"]
    assert case["routing"]["destination"] == "retirement_advisor_review"
    assert case["routing"]["recommended_advisor_ids"][0] == "ADV-01", "existing active advisor shown first"
    assert case["triage"]["status"] == "completed"
    assert len(case["conversation"]) == 3

    candidates = client.get(f"/staff/cases/{case_id}/candidates", headers=STAFF).json()["candidates"]
    assert [c["advisor_id"] for c in candidates][:2] == ["ADV-01", "ADV-03"]
    assert candidates[0]["existing_relationship"] is True
    assert all(c["reason"] for c in candidates)
    assert all("ADV-07" != c["advisor_id"] for c in candidates), "inactive advisors are never candidates"

    assigned = client.post(f"/staff/cases/{case_id}/assign", json={"advisor_id": "ADV-03", "staff_reason": "Rollover specialty, available sooner."}, headers=STAFF).json()
    assert assigned["status"] == "assigned" and assigned["assigned_advisor_id"] == "ADV-03"
    final = client.get(f"/staff/cases/{case_id}", headers=STAFF).json()
    assert final["status"] == "assigned"
    assert final["routing"]["staff_decision"]["staff_reason"] == "Rollover specialty, available sooner."
    assert final["history"][-1]["event"] == "assigned"
    row = next(c for c in client.get("/staff/cases", headers=STAFF).json()["cases"] if c["case_id"] == case_id)
    assert row["status"] == "assigned" and row["assigned_advisor_id"] == "ADV-03"


def test_clear_roth_question_is_not_over_clarified(client):
    sid = start(client, "CLIENT-022")
    first = turn(client, sid, CLEAR_ROTH)
    assert first["status"] == "ready_for_client_review"
    assert first["candidate_account_id"] == "ACCT-211"
    assert first["selected_account_id"] is None
    assert any(s["account_id"] == "ACCT-211" for s in first["suggestions"])
    result = confirm(client, sid, first["proposed_plain_language_request"], "ACCT-211")
    case = client.get(f"/staff/cases/{result['case_id']}", headers=STAFF).json()
    assert case["account_match_status"] == "client_confirmed"
    assert "client_term_did_not_match_account_type" not in case["flags"]
    assert case["amount_requested"] is None
    assert case["account_context"]["account_type"] == "roth_ira"
    assert case["routing"]["destination"] != "specialist_security_review"
    candidates = client.get(f"/staff/cases/{result['case_id']}/candidates", headers=STAFF).json()["candidates"]
    assert candidates[0]["advisor_id"] == "ADV-02", "existing advisor first"


def test_beneficiary_request_routes_to_estate_review(client):
    sid = start(client, "CLIENT-031")
    first = turn(client, sid, BENEFICIARY)
    assert first["candidate_intent"] == "update_beneficiary"
    assert any(d["term"] == "Beneficiary" for d in first["definitions"])
    result = confirm(client, sid, first["proposed_plain_language_request"], "ACCT-221")
    case = client.get(f"/staff/cases/{result['case_id']}", headers=STAFF).json()
    assert case["categories"][0] == "beneficiary_or_estate"
    assert case["routing"]["destination"] == "estate_planning_advisor_review"
    candidates = client.get(f"/staff/cases/{result['case_id']}/candidates", headers=STAFF).json()["candidates"]
    assert candidates[0]["advisor_id"] == "ADV-04"
    assert "beneficiary_or_estate" in candidates[0]["specialties"]


def test_security_concern_routes_to_specialist_queue(client):
    sid = start(client, "CLIENT-031")
    first = turn(client, sid, SECURITY)
    assert first["candidate_intent"] == "report_security_concern"
    result = confirm(client, sid, first["proposed_plain_language_request"], "ACCT-222")
    case = client.get(f"/staff/cases/{result['case_id']}", headers=STAFF).json()
    assert case["categories"][0] == "fraud_or_security"
    assert case["routing"]["destination"] == "specialist_security_review"
    assert case["urgency"]["level"] == "elevated"
    assert {"possible_unauthorized_access", "security_keywords_detected"} <= set(case["flags"])
    assert "ADV-04" not in case["routing"]["recommended_advisor_ids"], "existing general advisor is not recommended for security cases"
    body = client.get(f"/staff/cases/{result['case_id']}/candidates", headers=STAFF).json()
    assert body["destination"] == "specialist_security_review"
    assert [c["advisor_id"] for c in body["candidates"]] == ["ADV-08"]
    assert body["candidates"][0]["kind"] == "specialist_queue"
    row = next(c for c in client.get("/staff/cases", headers=STAFF).json()["cases"] if c["case_id"] == result["case_id"])
    assert row["urgency"]["level"] == "elevated"

    # Staff may still override; the override is recorded as a flag with the reason.
    assigned = client.post(f"/staff/cases/{result['case_id']}/assign", json={"advisor_id": "ADV-04", "staff_reason": "Client asked for her usual advisor; security desk notified separately."}, headers=STAFF).json()
    assert "staff_overrode_specialist_recommendation" in assigned["flags"]


def test_security_keywords_force_specialist_even_if_model_misses_them(tmp_path):
    from tests.backend.conftest import make_client_with_adapter

    def intake(client_id, transcript, selected_option_id, tools):
        return {"suggestions": [{"id": "opt-1", "label": "Something about your brokerage account", "account_id": "ACCT-222"}], "question": None, "candidate_intent": "general_question"}

    def triage(confirmed_request, tools):
        return {"client_summary": "x", "staff_summary": "General question.", "categories": ["account_service"], "flags": [], "unresolved_questions": []}

    with make_client_with_adapter(tmp_path, intake, triage) as client:
        sid = start(client, "CLIENT-031")
        turn(client, sid, SECURITY)
        result = confirm(client, sid, "Someone took money from my account and it was not me.", "ACCT-222")
        case = client.get(f"/staff/cases/{result['case_id']}", headers=STAFF).json()
        assert case["categories"][0] == "fraud_or_security"
        assert case["routing"]["destination"] == "specialist_security_review"
        assert "security_keywords_detected" in case["flags"]


def test_talk_to_person_hands_off_with_words_preserved(client):
    sid = start(client, "CLIENT-017")
    turn(client, sid, "I am confused about my accounts and would rather speak with someone.")
    handoff = turn(client, sid, option="talk_to_person")
    assert handoff["status"] == "ready_for_client_review"
    assert handoff["question"] is None
    assert handoff["proposed_plain_language_request"]
    result = confirm(client, sid, handoff["proposed_plain_language_request"])
    case = client.get(f"/staff/cases/{result['case_id']}", headers=STAFF).json()
    assert "client_requested_human_help" in case["flags"]
    assert case["account_match_status"] == "unresolved"
    assert "account_unresolved" in case["flags"]
    assert case["account_context"] is None
    assert any("account" in q.lower() for q in case["unresolved_questions"])
    row = next(c for c in client.get("/staff/cases", headers=STAFF).json()["cases"] if c["case_id"] == result["case_id"])
    assert row["clarification_needed"] is True


def test_none_of_these_clears_proposal_and_offers_other_accounts(client):
    sid = start(client, "CLIENT-017")
    first = turn(client, sid, ROTH_THING)
    offered = {s["account_id"] for s in first["suggestions"] if s["account_id"]}
    second = turn(client, sid, option="none_of_these")
    assert second["status"] == "needs_clarification"
    assert second["selected_account_id"] is None and second["candidate_account_id"] is None
    new_ids = {s["account_id"] for s in second["suggestions"] if s["account_id"]}
    assert new_ids and not (new_ids & offered), "offers accounts not shown before"
