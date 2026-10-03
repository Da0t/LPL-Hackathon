"""End-to-end synthetic scenarios from data/README.md: ambiguous IRA, clear Roth question,
beneficiary request, and the sign-in alert that must go to specialist review."""

from __future__ import annotations

from tests.backend.conftest import BENEFICIARY, CLEAR_ROTH, ROTH_THING, SECURITY, SEED_CASE_IDS, STAFF, confirm, start, turn


def test_ambiguous_roth_thing_end_to_end(client):
    sid = start(client, "CLIENT-017")

    first = turn(client, sid, ROTH_THING, mode="voice")
    assert first["status"] == "needs_clarification"
    assert "Roth IRA" in first["question"] and "rollover" in first["question"].lower()
    assert first["selected_account_id"] is None, "a model suggestion must not be auto-selected"
    assert [s["account_id"] for s in first["suggestions"] if s["account_id"]] == ["ACCT-201"]
    assert len(first["suggestions"]) <= 3
    assert {d["term"] for d in first["definitions"]} >= {"rollover IRA", "Roth IRA"}
    assert "no Roth IRA" in first["uncertainty"]

    yes = next(s for s in first["suggestions"] if s["account_id"] == "ACCT-201")
    second = turn(client, sid, option=yes["id"])
    assert second["selected_account_id"] == "ACCT-201", "client choice sets the account"
    assert second["status"] == "needs_clarification"
    assert "taking money out" in second["question"].lower()

    third = turn(client, sid, option="opt-withdraw")
    assert third["status"] == "ready_for_client_review" and third["question"] is None
    assert "$6,000" in third["proposed_plain_language_request"] and "****4821" in third["proposed_plain_language_request"]

    wording = "I want to speak with an advisor about using $6,000 from my retirement account from my former employer."
    result = confirm(client, sid, wording, "ACCT-201", 6000)
    assert result["status"] == "submitted" and result["case_id"] == "CASE-1043"
    case_id = result["case_id"]

    queue = client.get("/staff/cases", headers=STAFF).json()["cases"]
    assert queue[0]["case_id"] == case_id and {c["case_id"] for c in queue} >= SEED_CASE_IDS
    row = queue[0]
    assert row["status"] == "submitted"
    assert row["categories"] == ["withdrawal_or_distribution", "retirement_income"]
    assert "client_term_did_not_match_account_type" in row["flags"]
    assert row["confirmed_plain_language_request"] == wording

    case = client.get(f"/staff/cases/{case_id}", headers=STAFF).json()
    assert case["status"] == "staff_review", "opening the case moves it to staff review"
    assert case["original_words"] == ROTH_THING and case["input_mode"] in {"voice", "mixed"}
    assert case["amount_requested"] == 6000 and case["currency"] == "USD"
    assert case["selected_account_id"] == "ACCT-201" and case["account_match_status"] == "client_confirmed"
    ctx = case["account_context"]
    assert (ctx["account_type"], ctx["masked_identifier"], ctx["balance"], ctx["balance_as_of"]) == ("rollover_ira", "****4821", 84000, "2026-10-01")
    assert ctx["account_source_id"] == "ACCOUNT-RECORD-201"
    assert [e["source_id"] for e in ctx["relevant_events"]] == ["EVENT-09"], "only events relevant to the categories; the address update is not shown"
    assert ctx["relevant_events"][0]["type"] == "rollover" and ctx["relevant_events"][0]["summary"]
    assert ctx["familiar_label"] == "Retirement account from former employer"
    assert any("no Roth IRA" in c["statement"] for c in case["conflicts"]) and case["conflicts"][0]["source_id"] == "ACCOUNT-RECORD-201"
    assert "rollover IRA" in case["staff_summary"] and "$6,000" in case["staff_summary"]
    assert case["routing"]["destination"] == "retirement_advisor_review" and case["routing"]["reason"]
    assert case["routing"]["recommended_advisor_ids"][0] == "ADV-03"
    assert case["routing"]["staff_decision"] is None
    assert case["triage"]["status"] == "completed" and len(case["conversation"]) == 3
    assert case["client_confirmed_at"] and case["preferred_contact_channel"] == "phone"

    candidates = client.get(f"/staff/cases/{case_id}/candidates", headers=STAFF).json()["candidates"]
    assert [c["advisor_id"] for c in candidates] == ["ADV-03", "ADV-04", "ADV-06"], "available specialty matches; nobody at capacity, nobody inactive"
    assert candidates[0]["existing_client_relationship"] is False and candidates[0]["meeting_mode"] == ["phone", "video"]
    assert all(c["reason"] for c in candidates) and "ADV-08" not in {c["advisor_id"] for c in candidates}

    assigned = client.post(f"/staff/cases/{case_id}/assign", json={"advisor_id": "ADV-03", "staff_reason": "Retirement-income specialty, available, offers phone meetings."}, headers=STAFF).json()
    assert assigned["status"] == "assigned" and assigned["assigned_advisor_id"] == "ADV-03"
    final = client.get(f"/staff/cases/{case_id}", headers=STAFF).json()
    assert final["status"] == "assigned"
    assert final["routing"]["staff_decision"] == "Retirement-income specialty, available, offers phone meetings.", "a string, as the staff page renders it"
    assert final["routing"]["staff_decision_detail"]["advisor_id"] == "ADV-03"
    assert final["history"][-1]["event"] == "assigned"
    row = next(c for c in client.get("/staff/cases", headers=STAFF).json()["cases"] if c["case_id"] == case_id)
    assert row["status"] == "assigned" and row["routing"]["assigned_advisor_id"] == "ADV-03"


def test_clear_roth_question_is_not_over_clarified(client):
    sid = start(client, "CLIENT-022")
    first = turn(client, sid, CLEAR_ROTH, client_id="CLIENT-022")
    assert first["status"] == "ready_for_client_review"
    assert first["candidate_account_id"] == "ACCT-301" and first["selected_account_id"] is None
    assert any(s["account_id"] == "ACCT-301" for s in first["suggestions"])
    assert first["candidate_intent"] == "discuss_contribution"
    result = confirm(client, sid, first["proposed_plain_language_request"], "ACCT-301", client_id="CLIENT-022")
    case = client.get(f"/staff/cases/{result['case_id']}", headers=STAFF).json()
    assert case["account_match_status"] == "client_confirmed"
    assert "client_term_did_not_match_account_type" not in case["flags"] and case["conflicts"] == []
    assert case["amount_requested"] is None and case["currency"] is None
    assert case["account_context"]["account_type"] == "roth_ira"
    assert case["categories"] == ["investment_planning", "account_service"]
    candidates = client.get(f"/staff/cases/{result['case_id']}/candidates", headers=STAFF).json()["candidates"]
    assert candidates[0]["advisor_id"] == "ADV-01" and candidates[0]["existing_client_relationship"] is True, "existing advisor first"


def test_beneficiary_request_routes_to_estate_review(client):
    sid = start(client, "CLIENT-031")
    first = turn(client, sid, BENEFICIARY, mode="voice", client_id="CLIENT-031")
    assert first["candidate_intent"] == "update_beneficiary"
    assert first["candidate_account_id"] == "ACCT-401"
    assert any(d["term"] == "beneficiary" for d in first["definitions"])
    result = confirm(client, sid, first["proposed_plain_language_request"], "ACCT-401", client_id="CLIENT-031")
    case = client.get(f"/staff/cases/{result['case_id']}", headers=STAFF).json()
    assert case["categories"][0] == "beneficiary_or_estate"
    assert case["routing"]["destination"] == "estate_and_beneficiary_review"
    event_ids = [e["source_id"] for e in case["account_context"]["relevant_events"]]
    assert event_ids[0] == "EVENT-31", "the beneficiary designation explains this request and comes first"
    assert "EVENT-35" not in event_ids, "events from other accounts never appear"
    candidates = client.get(f"/staff/cases/{result['case_id']}/candidates", headers=STAFF).json()["candidates"]
    assert candidates[0]["advisor_id"] == "ADV-07" and candidates[0]["existing_client_relationship"] is True
    assert candidates[1]["advisor_id"] == "ADV-02"


def test_sign_in_alert_routes_to_specialist_queue(client):
    sid = start(client, "CLIENT-022")
    first = turn(client, sid, SECURITY, client_id="CLIENT-022")
    assert first["candidate_intent"] == "review_account_access"
    assert first["status"] == "ready_for_client_review", "security concerns are not interrogated"
    result = confirm(client, sid, "I need help reviewing an account sign-in I do not recognize.", None, client_id="CLIENT-022")
    case = client.get(f"/staff/cases/{result['case_id']}", headers=STAFF).json()
    assert case["categories"][0] == "fraud_or_security"
    assert case["routing"]["destination"] == "security_specialist_review"
    assert case["routing"]["recommended_advisor_ids"] == []
    assert case["urgency"]["level"] == "elevated"
    assert case["account_match_status"] == "not_needed" and case["account_context"] is None
    assert {"possible_unauthorized_access", "security_keywords_detected"} <= set(case["flags"])
    body = client.get(f"/staff/cases/{result['case_id']}/candidates", headers=STAFF).json()
    assert body["destination"] == "security_specialist_review" and body["candidates"] == [] and body["reason"]
    row = next(c for c in client.get("/staff/cases", headers=STAFF).json()["cases"] if c["case_id"] == result["case_id"])
    assert row["urgency"]["level"] == "elevated" and row["routing"]["destination"] == "security_specialist_review"

    # Staff may still override; the override is recorded as a flag with the reason.
    assigned = client.post(f"/staff/cases/{result['case_id']}/assign", json={"advisor_id": "ADV-01", "staff_reason": "Security desk notified separately; client asked for her usual advisor."}, headers=STAFF).json()
    assert "staff_overrode_specialist_recommendation" in assigned["flags"]


def test_security_keywords_force_specialist_even_if_model_misses_them(tmp_path):
    from tests.backend.conftest import make_client_with_adapter

    def intake(client_id, transcript, selected_option_id, tools):
        return {"suggestions": [{"id": "ACCT-302", "label": "Long-term investment account", "account_id": "ACCT-302"}], "question": None, "candidate_intent": "general_question"}

    def triage(confirmed_request, tools):
        return {"client_summary": "x", "staff_summary": "General question.", "categories": ["account_service"], "flags": [], "unresolved_questions": []}

    with make_client_with_adapter(tmp_path, intake, triage) as client:
        sid = start(client, "CLIENT-022")
        turn(client, sid, "Someone moved money out of my brokerage account and I didn't do it.", client_id="CLIENT-022")
        result = confirm(client, sid, "Someone took money from my account and it was not me.", "ACCT-302", client_id="CLIENT-022")
        case = client.get(f"/staff/cases/{result['case_id']}", headers=STAFF).json()
        assert case["categories"][0] == "fraud_or_security"
        assert case["routing"]["destination"] == "security_specialist_review"
        assert "security_keywords_detected" in case["flags"]
        assert case["account_match_status"] == "client_confirmed"


def test_seeded_cases_populate_the_queue_for_the_demo(client):
    rows = {c["case_id"]: c for c in client.get("/staff/cases", headers=STAFF).json()["cases"]}
    assert SEED_CASE_IDS <= set(rows)
    assert rows["CASE-1042"]["status"] == "submitted" and rows["CASE-1042"]["routing"]["assigned_advisor_id"] is None
    assert rows["CASE-SEC-1"]["routing"]["destination"] == "security_specialist_review"
    sec = client.get("/staff/cases/CASE-SEC-1", headers=STAFF).json()
    assert sec["categories"] == ["fraud_or_security", "account_service"] and sec["account_match_status"] == "not_needed"
    assert client.get("/staff/cases/CASE-SEC-1/candidates", headers=STAFF).json()["candidates"] == []
    fixture_case = client.get("/staff/cases/CASE-1042", headers=STAFF).json()
    assert fixture_case["account_context"]["account_source_id"] == "ACCOUNT-RECORD-201"
    assert fixture_case["account_context"]["relevant_events"][0]["source_id"] == "EVENT-09"
    assert any("Roth" in c["statement"] for c in fixture_case["conflicts"]), "seed case gets the same sourced conflict statement"
    assert client.get("/staff/cases/CASE-1042/candidates", headers=STAFF).json()["candidates"][0]["advisor_id"] == "ADV-03"


def test_talk_to_person_hands_off_with_words_preserved(client):
    sid = start(client, "CLIENT-017")
    turn(client, sid, "I am confused about my accounts and would rather speak with someone.")
    handoff = turn(client, sid, option="talk_to_person")
    assert handoff["status"] == "ready_for_client_review" and handoff["question"] is None
    assert handoff["proposed_plain_language_request"]
    result = confirm(client, sid, handoff["proposed_plain_language_request"])
    case = client.get(f"/staff/cases/{result['case_id']}", headers=STAFF).json()
    assert "client_requested_human_help" in case["flags"]
    assert case["account_match_status"] == "unresolved" and "account_unresolved" in case["flags"]
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
    assert new_ids == {"ACCT-202"} and not (new_ids & offered), "offers accounts not shown before"
