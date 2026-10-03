"""The seven frozen endpoints return the contract field names from contracts/API_V1.md (plus additive extras)."""

from __future__ import annotations

import json

from backend.settings import REPO_ROOT
from tests.backend.conftest import CLIENT, ROTH_THING, STAFF, confirm, start, submit_roth_thing_case, turn

CONTRACT_TURN_FIELDS = {"session_id", "transcript", "suggestions", "question", "definitions", "candidate_intent", "selected_account_id", "uncertainty", "status"}
CONTRACT_QUEUE_FIELDS = {"case_id", "client_display_name", "created_at", "status", "categories", "flags", "confirmed_plain_language_request"}
CONTRACT_CANDIDATE_FIELDS = {"advisor_id", "display_name", "specialties", "available", "reason"}
CONTRACT_CASE_FIELDS = {
    "case_id", "client_id", "client_display_name", "created_at", "status", "input_mode", "original_words",
    "confirmed_plain_language_request", "staff_summary", "intent", "amount_requested", "currency", "selected_account_id",
    "account_match_status", "categories", "unresolved_questions", "flags", "account_context", "routing",
}


def test_intake_start_contract(client):
    response = client.post("/intake/start", json={"client_id": "CLIENT-017"}, headers=CLIENT)
    assert response.status_code == 200
    body = response.json()
    assert {"session_id", "client_display_name", "status"} <= set(body)
    assert body["status"] == "draft"
    assert body["client_display_name"] == "Mara Ellis"
    assert body["ai_mode"] == "mock"


def test_intake_turn_contract(client):
    sid = start(client)
    body = turn(client, sid, ROTH_THING, mode="voice")
    assert CONTRACT_TURN_FIELDS <= set(body)
    assert 1 <= len(body["suggestions"]) <= 3
    for suggestion in body["suggestions"]:
        assert {"id", "label", "account_id"} <= set(suggestion)
    for definition in body["definitions"]:
        assert set(definition) == {"term", "plain"}
    assert body["status"] in {"needs_clarification", "ready_for_client_review"}
    assert body["transcript"] == ROTH_THING


def test_intake_confirm_contract(client):
    sid = start(client)
    turn(client, sid, ROTH_THING)
    body = confirm(client, sid, "I want to talk about money from my rollover IRA.", "ACCT-201", 6000)
    assert {"case_id", "status", "client_summary"} <= set(body)
    assert body["case_id"] == "CASE-1043", "live cases continue after the seeded CASE-1042, as in the contract example"
    assert body["status"] == "submitted"
    assert body["client_summary"]


def test_staff_queue_contract(client):
    case_id = submit_roth_thing_case(client)
    response = client.get("/staff/cases", headers=STAFF)
    assert response.status_code == 200
    cases = response.json()["cases"]
    assert cases[0]["case_id"] == case_id, "newest first"
    for row in cases:
        assert CONTRACT_QUEUE_FIELDS <= set(row)
        assert "destination" in row["routing"]


def test_staff_case_detail_matches_fixture_shape(client):
    case_id = submit_roth_thing_case(client)
    body = client.get(f"/staff/cases/{case_id}", headers=STAFF).json()
    assert CONTRACT_CASE_FIELDS <= set(body)
    fixture = json.loads((REPO_ROOT / "contracts" / "demo_fixture_v1.json").read_text())["cases"][0]
    assert set(fixture) <= set(body), "every key in the frozen fixture case is present"
    assert set(fixture["routing"]) <= set(body["routing"])
    assert set(fixture["account_context"]) <= set(body["account_context"])
    assert all({"type", "date", "source_id"} <= set(e) for e in body["account_context"]["relevant_events"])


def test_staff_candidates_contract(client):
    case_id = submit_roth_thing_case(client)
    body = client.get(f"/staff/cases/{case_id}/candidates", headers=STAFF).json()
    assert 1 <= len(body["candidates"]) <= 3
    for candidate in body["candidates"]:
        assert CONTRACT_CANDIDATE_FIELDS <= set(candidate)
        assert candidate["eligibility_check"] == "manual_verification_required"
        assert "existing_client_relationship" in candidate and "meeting_mode" in candidate and "capacity" in candidate


def test_staff_assign_contract(client):
    case_id = submit_roth_thing_case(client)
    response = client.post(f"/staff/cases/{case_id}/assign", json={"advisor_id": "ADV-03", "staff_reason": "Retirement-income specialty and available."}, headers=STAFF)
    assert response.status_code == 200
    body = response.json()
    assert {"case_id", "status", "assigned_advisor_id"} <= set(body)
    assert (body["case_id"], body["status"], body["assigned_advisor_id"]) == (case_id, "assigned", "ADV-03")


def test_error_envelope_shapes(client):
    missing = client.get("/staff/cases/CASE-9999", headers=STAFF)
    assert missing.status_code == 404 and missing.json()["error_code"] == "CASE_NOT_FOUND"
    invalid = client.post("/intake/start", json={}, headers=CLIENT)
    assert invalid.status_code == 422 and invalid.json()["error_code"] == "VALIDATION_ERROR"
    not_json = client.post("/intake/start", content="{nope", headers={**CLIENT, "Content-Type": "application/json"})
    assert not_json.status_code == 400 and not_json.json()["error_code"] == "INVALID_JSON"
    unknown_route = client.get("/does-not-exist")
    assert unknown_route.status_code == 404 and unknown_route.json()["error_code"] == "PATH_NOT_FOUND"
    bad_role = client.get("/staff/cases", headers={"X-Demo-Role": "admin"})
    assert bad_role.status_code == 400 and bad_role.json()["error_code"] == "INVALID_ROLE"
    for response in (missing, invalid, not_json, unknown_route, bad_role):
        assert {"error_code", "message"} <= set(response.json())


def test_openapi_lists_frozen_paths(client):
    paths = set(client.get("/openapi.json").json()["paths"])
    assert {
        "/intake/start", "/intake/{session_id}/turn", "/intake/{session_id}/confirm",
        "/staff/cases", "/staff/cases/{case_id}", "/staff/cases/{case_id}/candidates", "/staff/cases/{case_id}/assign",
    } <= paths
