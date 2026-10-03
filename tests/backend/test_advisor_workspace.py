"""Advisor workspace additions: queue priority, lifecycle, client snapshot, next-steps and investigation endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.services.priority import lifecycle_of, priority_for
from tests.backend.conftest import STAFF

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)


def case(**overrides):
    base = {"status": "submitted", "categories": ["account_service"], "created_at": "2026-10-03T09:00:00Z",
            "urgency": None, "routing": {"assigned_advisor_id": None}, "history": []}
    base.update(overrides)
    return base


def event(name):
    return {"event": name, "at": "2026-10-03T10:00:00Z", "details": {}}


# ------------------------------------------------------------- priority (pure)


def test_security_cases_are_urgent_ahead_of_everything_else():
    p = priority_for(case(categories=["fraud_or_security"]), NOW)
    assert p["level"] == "urgent" and p["rank"] == 0 and "security" in p["reason"].lower()


def test_new_case_reports_how_long_it_has_waited():
    assert priority_for(case(), NOW) == {"level": "normal", "rank": 2, "reason": "New, waiting 3 hours for an advisor"}


def test_unassigned_case_waiting_over_a_day_is_high_priority():
    p = priority_for(case(created_at="2026-10-01T09:00:00Z"), NOW)
    assert p["level"] == "high" and p["reason"] == "Waiting 2 days for an advisor"


def test_case_waiting_on_the_client_is_low_priority():
    p = priority_for(case(status="needs_client_followup"), NOW)
    assert p["level"] == "low" and "client" in p["reason"].lower()


def test_resolved_case_is_done_even_if_it_is_a_security_case():
    p = priority_for(case(categories=["fraud_or_security"], history=[event("request_resolved")]), NOW)
    assert p["level"] == "done" and p["rank"] == 4


def test_lifecycle_follows_assignment_scheduling_and_resolution():
    assert lifecycle_of(case()) == "new"
    assert lifecycle_of(case(status="needs_client_followup")) == "awaiting_client"
    assert lifecycle_of(case(status="assigned", routing={"assigned_advisor_id": "ADV-01"})) == "assigned"
    assert lifecycle_of(case(status="assigned", history=[event("meeting_scheduled")])) == "scheduled"
    assert lifecycle_of(case(history=[event("meeting_scheduled"), event("request_resolved")])) == "resolved"


# ------------------------------------------------------------- queue summary


def test_queue_rows_carry_priority_and_lifecycle(client):
    rows = {c["case_id"]: c for c in client.get("/staff/cases", headers=STAFF).json()["cases"]}
    assert rows["CASE-SEC-1"]["priority"]["level"] == "urgent"
    assert rows["CASE-1042"]["lifecycle"] == "new" and rows["CASE-1042"]["priority"]["reason"]


def test_resolving_a_case_survives_a_reload_of_the_queue(client):
    client.post("/staff/cases/CASE-1040/action", json={"action": "resolve", "text": "Answered by phone."}, headers=STAFF)
    row = next(c for c in client.get("/staff/cases", headers=STAFF).json()["cases"] if c["case_id"] == "CASE-1040")
    assert row["lifecycle"] == "resolved" and row["priority"]["level"] == "done"


# ------------------------------------------------------------- client snapshot


def test_client_snapshot_shows_the_whole_client_from_the_records(client):
    response = client.get("/staff/cases/CASE-1040/client", headers=STAFF)
    assert response.status_code == 200, response.text
    snap = response.json()
    assert snap["client"]["display_name"] == "Evan Brooks" and snap["client"]["meeting_preference"] == "video"
    assert snap["usual_advisor"] == {"advisor_id": "ADV-01", "display_name": "Taylor Morgan"}
    accounts = {a["masked_identifier"]: a for a in snap["accounts"]}
    assert accounts["****1187"]["label"] == "Brokerage account" and accounts["****1187"]["balance"] == 38400
    assert any(e["type"] == "security_alert" and e["masked_identifier"] == "****1187" for e in snap["recent_events"])
    assert [e["date"] for e in snap["recent_events"]] == sorted((e["date"] for e in snap["recent_events"]), reverse=True)
    assert [c["case_id"] for c in snap["other_cases"]] == ["CASE-SEC-1"], "the client's other request, not this one"


def test_client_snapshot_names_the_assigned_advisor(client):
    client.post("/staff/cases/CASE-1040/assign", json={"advisor_id": "ADV-01", "staff_reason": "Existing relationship."}, headers=STAFF)
    snap = client.get("/staff/cases/CASE-1040/client", headers=STAFF).json()
    assert snap["assigned_advisor"]["display_name"] == "Taylor Morgan"


def test_client_snapshot_does_not_mark_the_case_as_reviewed(client):
    client.get("/staff/cases/CASE-1042/client", headers=STAFF)
    row = next(c for c in client.get("/staff/cases", headers=STAFF).json()["cases"] if c["case_id"] == "CASE-1042")
    assert row["status"] == "submitted"


# ------------------------------------------------------------- next-steps planner (mock mode)


def test_next_steps_for_a_withdrawal_start_with_the_account_mismatch(client):
    response = client.post("/staff/cases/CASE-1042/next-steps", json={}, headers=STAFF)
    assert response.status_code == 200, response.text
    plan = response.json()
    assert plan["ai_mode"] == "mock" and plan["summary"]
    titles = [s["title"] for s in plan["steps"]]
    assert titles[0] == "Confirm the account with the client"
    assert any("distribution" in t.lower() for t in titles)
    assert {s["owner"] for s in plan["steps"]} <= {"advisor", "client", "operations"}
    assert all(s["detail"] for s in plan["steps"])
    assert titles[-1] == "Schedule the conversation" and "phone" in plan["steps"][-1]["detail"]


def test_next_steps_turn_open_questions_into_client_and_advisor_steps(client):
    steps = client.post("/staff/cases/CASE-1042/next-steps", json={}, headers=STAFF).json()["steps"]
    by_title = {s["title"]: s for s in steps}
    assert by_title["Ask the client: desired timing"]["owner"] == "client"
    assert by_title["Review: potential tax implications"]["owner"] == "advisor"


# ------------------------------------------------------------- fraud investigator (mock mode)


def test_investigation_builds_the_timeline_from_account_records(client):
    response = client.post("/staff/cases/CASE-SEC-1/investigation", json={}, headers=STAFF)
    assert response.status_code == 200, response.text
    inv = response.json()
    assert inv["risk_level"] == "high"
    alert = next(t for t in inv["timeline"] if t["source_id"] == "EVENT-24")
    assert alert["highlight"] is True and alert["date"] == "2026-10-02" and "****1187" in alert["account"]
    assert inv["timeline"][-1]["source_id"] == "CASE-SEC-1", "the client's report closes the timeline"
    assert [t["date"] for t in inv["timeline"]] == sorted(t["date"] for t in inv["timeline"])
    assert any("EVENT-24" in r for r in inv["reasons"]) and len(inv["recommended_steps"]) >= 3


def test_investigation_is_only_for_security_cases(client):
    response = client.post("/staff/cases/CASE-1042/investigation", json={}, headers=STAFF)
    assert response.status_code == 400 and response.json()["error_code"] == "NOT_A_SECURITY_CASE"


def test_new_endpoints_require_staff(client):
    headers = {"X-Demo-Role": "client", "X-Demo-Client-Id": "CLIENT-017"}
    assert client.get("/staff/cases/CASE-1042/client", headers=headers).status_code == 403
    assert client.post("/staff/cases/CASE-1042/next-steps", json={}, headers=headers).status_code == 403
    assert client.post("/staff/cases/CASE-SEC-1/investigation", json={}, headers=headers).status_code == 403
