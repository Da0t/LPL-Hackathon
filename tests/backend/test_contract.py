"""The seven frozen endpoints return exactly the contract field names (plus additive extras)."""

from __future__ import annotations

from tests.backend.conftest import CLIENT, ROTH_THING, STAFF, confirm, start, submit_roth_thing_case, turn

CONTRACT_TURN_FIELDS = {"session_id", "transcript", "suggestions", "question", "definitions", "candidate_intent", "selected_account_id", "uncertainty", "status"}
CONTRACT_QUEUE_FIELDS = {"case_id", "client_display_name", "created_at", "status", "categories", "flags", "confirmed_plain_language_request"}
CONTRACT_CANDIDATE_FIELDS = {"advisor_id", "display_name", "specialties", "available", "reason"}
CONTRACT_CASE_FIELDS = {
    "case_id", "client_id", "status", "input_mode", "original_words", "confirmed_plain_language_request", "staff_summary",
    "intent", "amount_requested", "currency", "selected_account_id", "account_match_status", "categories",
    "unresolved_questions", "flags", "account_context", "routing",
}


def test_intake_start_contract(client):
    response = client.post("/intake/start", json={"client_id": "CLIENT-017"}, headers=CLIENT)
    assert response.status_code == 200
    body = response.json()
    assert {"session_id", "client_display_name", "status"} <= set(body)
    assert body["status"] == "draft"
    assert body["client_display_name"] == "Margaret Ellison"
    assert body["agent_mode"] == "mock"


def test_intake_turn_contract(client):
    sid = start(client)
    body = turn(client, sid, ROTH_THING, mode="voice")
    assert CONTRACT_TURN_FIELDS <= set(body)
    assert len(body["suggestions"]) <= 3
    for suggestion in body["suggestions"]:
        assert {"id", "label"} <= set(suggestion)
        assert "account_id" in suggestion
    for definition in body["definitions"]:
        assert set(definition) == {"term", "plain"}
    assert body["status"] in {"needs_clarification", "ready_for_client_review"}
    assert body["transcript"] == ROTH_THING


def test_intake_confirm_contract(client):
    sid = start(client)
    turn(client, sid, ROTH_THING)
    body = confirm(client, sid, "I want to talk about money from my rollover IRA.", "ACCT-201", 6000)
    assert {"case_id", "status", "client_summary"} <= set(body)
    assert body["case_id"].startswith("CASE-")
    assert body["status"] == "submitted"


def test_staff_queue_contract(client):
    case_id = submit_roth_thing_case(client)
    response = client.get("/staff/cases", headers=STAFF)
    assert response.status_code == 200
    cases = response.json()["cases"]
    assert cases and cases[0]["case_id"] == case_id
    assert CONTRACT_QUEUE_FIELDS <= set(cases[0])


def test_staff_case_detail_contract(client):
    case_id = submit_roth_thing_case(client)
    body = client.get(f"/staff/cases/{case_id}", headers=STAFF).json()
    assert CONTRACT_CASE_FIELDS <= set(body)
    assert {"destination", "recommended_advisor_ids", "assigned_advisor_id", "staff_decision"} <= set(body["routing"])
    ctx = body["account_context"]
    assert {"account_type", "masked_identifier", "balance", "balance_as_of", "relevant_events"} <= set(ctx)
    assert all({"type", "date", "source_id"} <= set(e) for e in ctx["relevant_events"])


def test_staff_candidates_contract(client):
    case_id = submit_roth_thing_case(client)
    body = client.get(f"/staff/cases/{case_id}/candidates", headers=STAFF).json()
    assert "candidates" in body
    assert 1 <= len(body["candidates"]) <= 3
    for candidate in body["candidates"]:
        assert CONTRACT_CANDIDATE_FIELDS <= set(candidate)
        assert candidate["eligibility_check"] == "manual_verification_required"


def test_staff_assign_contract(client):
    case_id = submit_roth_thing_case(client)
    response = client.post(f"/staff/cases/{case_id}/assign", json={"advisor_id": "ADV-01", "staff_reason": "Existing advisor"}, headers=STAFF)
    assert response.status_code == 200
    body = response.json()
    assert {"case_id", "status", "assigned_advisor_id"} <= set(body)
    assert body == {**body, "case_id": case_id, "status": "assigned", "assigned_advisor_id": "ADV-01"}


def test_error_envelope_shapes(client):
    missing = client.get("/staff/cases/CASE-9999", headers=STAFF)
    assert missing.status_code == 404
    assert set(missing.json()) >= {"error_code", "message"}
    invalid = client.post("/intake/start", json={}, headers=CLIENT)
    assert invalid.status_code == 422
    assert invalid.json()["error_code"] == "validation_error"
    unknown_route = client.get("/does-not-exist")
    assert unknown_route.status_code == 404
    assert unknown_route.json()["error_code"] == "not_found"
    bad_role = client.get("/staff/cases", headers={"X-Demo-Role": "admin"})
    assert bad_role.status_code == 400
    assert bad_role.json()["error_code"] == "invalid_role"


def test_openapi_lists_frozen_paths(client):
    paths = set(client.get("/openapi.json").json()["paths"])
    assert {
        "/intake/start", "/intake/{session_id}/turn", "/intake/{session_id}/confirm",
        "/staff/cases", "/staff/cases/{case_id}", "/staff/cases/{case_id}/candidates", "/staff/cases/{case_id}/assign",
    } <= paths
