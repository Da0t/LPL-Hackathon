"""Closing the loops: client replies, security escalation, agent-output caching, compliance on send."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.aws import advisor_agents as aa
from backend.aws import bedrock_agent as ba
from backend.main import create_app
from backend.services.agent_adapter import MockAdapter
from tests.backend.conftest import STAFF, client_headers, make_settings

MARA = client_headers("CLIENT-017")
EVAN = client_headers("CLIENT-022")
QUESTION = "Hi Mara, when would you like to talk?"


def clarify(client, case_id="CASE-1042", text=QUESTION, **extra):
    return client.post(f"/staff/cases/{case_id}/action", json={"action": "clarify", "text": text, **extra}, headers=STAFF)


def row(client, case_id):
    return next(c for c in client.get("/staff/cases", headers=STAFF).json()["cases"] if c["case_id"] == case_id)


# ------------------------------------------------------------- the client sees and answers advisor messages


def test_client_sees_only_their_own_requests_without_staff_fields(client):
    client.post("/staff/cases/CASE-1042/action", json={"action": "note", "text": "Internal: check tax."}, headers=STAFF)
    response = client.get("/my/requests", headers=MARA)
    assert response.status_code == 200, response.text
    requests = response.json()["requests"]
    assert [r["case_id"] for r in requests] == ["CASE-1042"]
    assert set(requests[0]) == {"case_id", "created_at", "request", "lifecycle", "awaiting_reply", "messages"}
    assert requests[0]["messages"] == [] and requests[0]["awaiting_reply"] is False, "staff notes are never shown to the client"


def test_advisor_message_reaches_the_client(client):
    assert clarify(client).status_code == 200
    request = client.get("/my/requests", headers=MARA).json()["requests"][0]
    assert request["awaiting_reply"] is True and request["lifecycle"] == "awaiting_client"
    assert [(m["from"], m["text"]) for m in request["messages"]] == [("advisor", QUESTION)]


def test_client_reply_returns_the_case_to_the_advisor_as_high_priority(client):
    clarify(client)
    response = client.post("/my/requests/CASE-1042/reply", json={"text": " Thursday afternoon works. "}, headers=MARA)
    assert response.status_code == 200, response.text
    request = client.get("/my/requests", headers=MARA).json()["requests"][0]
    assert request["awaiting_reply"] is False
    assert [(m["from"], m["text"]) for m in request["messages"]] == [("advisor", QUESTION), ("client", "Thursday afternoon works.")]
    queue_row = row(client, "CASE-1042")
    assert queue_row["status"] == "staff_review" and queue_row["lifecycle"] == "new"
    assert queue_row["priority"] == {"level": "high", "rank": 1, "reason": "The client replied"}
    history = client.get("/staff/cases/CASE-1042", headers=STAFF).json()["history"]
    assert history[-1]["event"] == "client_replied" and history[-1]["details"]["text"] == "Thursday afternoon works."


def test_reply_on_an_assigned_case_goes_back_to_assigned(client):
    client.post("/staff/cases/CASE-1042/assign", json={"advisor_id": "ADV-03", "staff_reason": "Fit."}, headers=STAFF)
    clarify(client)
    client.post("/my/requests/CASE-1042/reply", json={"text": "Friday."}, headers=MARA)
    assert row(client, "CASE-1042")["status"] == "assigned"


def test_the_reply_flag_clears_once_the_advisor_acts(client):
    clarify(client)
    client.post("/my/requests/CASE-1042/reply", json={"text": "Friday."}, headers=MARA)
    client.post("/staff/cases/CASE-1042/action", json={"action": "note", "text": "Booked."}, headers=STAFF)
    assert row(client, "CASE-1042")["priority"]["reason"] != "The client replied"


def test_client_reply_is_refused_when_it_should_be(client):
    assert client.post("/my/requests/CASE-1042/reply", json={"text": "Hello?"}, headers=MARA).json()["error_code"] == "NOT_AWAITING_REPLY"
    clarify(client)
    assert client.post("/my/requests/CASE-1042/reply", json={"text": "Mine now."}, headers=EVAN).status_code == 403
    assert client.post("/my/requests/CASE-1042/reply", json={"text": "  "}, headers=MARA).json()["error_code"] == "MISSING_TEXT"
    assert client.post("/my/requests/NOPE/reply", json={"text": "x"}, headers=MARA).status_code == 404
    assert client.get("/my/requests", headers=STAFF).status_code == 403
    assert client.get("/my/requests", headers={"X-Demo-Role": "client"}).json()["error_code"] == "MISSING_DEMO_CLIENT"


# ------------------------------------------------------------- security escalation


def test_security_case_can_be_sent_to_the_specialist_team(client):
    response = client.post("/staff/cases/CASE-SEC-1/action", json={"action": "escalate"}, headers=STAFF)
    assert response.status_code == 200 and response.json()["event"]["event"] == "escalated_to_security"
    queue_row = row(client, "CASE-SEC-1")
    assert queue_row["lifecycle"] == "assigned"
    assert queue_row["priority"]["level"] == "normal" and queue_row["priority"]["reason"] == "With the security specialist team"


def test_only_security_cases_can_be_escalated(client):
    response = client.post("/staff/cases/CASE-1042/action", json={"action": "escalate"}, headers=STAFF)
    assert response.status_code == 400 and response.json()["error_code"] == "NOT_A_SECURITY_CASE"


# ------------------------------------------------------------- compliance is checked by the server on send


def test_flagged_message_is_refused_without_an_override_and_the_case_is_untouched(client):
    response = clarify(client, text="Hi Mara, I recommend you withdraw it all.")
    assert response.status_code == 409 and response.json()["error_code"] == "COMPLIANCE_REVIEW_FAILED"
    assert row(client, "CASE-1042")["lifecycle"] == "new"


def test_flagged_message_sends_with_an_override_and_records_it(client):
    response = clarify(client, text="Hi Mara, I recommend you withdraw it all.", compliance={"override": True})
    assert response.status_code == 200, response.text
    assert response.json()["event"]["details"]["compliance"] == {"verdict": "needs_changes", "override": True}


def test_the_recorded_verdict_is_the_servers_not_the_browsers(client):
    response = clarify(client, compliance={"verdict": "needs_changes", "override": True})
    assert response.json()["event"]["details"]["compliance"] == {"verdict": "pass", "override": False}


# ------------------------------------------------------------- agent output is cached until the case changes


@pytest.fixture
def live(tmp_path):
    """An app in bedrock mode; tests patch the live agent functions to count calls."""
    adapter = MockAdapter()
    adapter.live = True  # create_app refuses a non-live adapter in bedrock mode
    with TestClient(create_app(make_settings(tmp_path, ai_mode="bedrock"), adapter=adapter)) as test_client:
        yield test_client


def counting(monkeypatch, module, name, result):
    calls = []

    def fake(*args, **kwargs):
        calls.append(args)
        return dict(result)

    monkeypatch.setattr(module, name, fake)
    return calls


PLAN = {"summary": "Do it.", "steps": [{"title": "Call", "detail": "Call the client.", "owner": "advisor"}]}
BRIEF = {"headline": "H", "talking_points": [], "confirm": [], "cautions": ["c"]}


def test_next_steps_run_the_model_once_until_refreshed_or_the_case_changes(live, monkeypatch):
    calls = counting(monkeypatch, aa, "plan_next_steps", PLAN)
    url = "/staff/cases/CASE-1041/next-steps"
    first = live.post(url, headers=STAFF)
    assert first.status_code == 200, "a POST with no body is accepted"
    assert live.post(url, json={}, headers=STAFF).json() == first.json() and len(calls) == 1
    live.post(url, json={"refresh": True}, headers=STAFF)
    assert len(calls) == 2, "Regenerate bypasses the cache"
    live.post("/staff/cases/CASE-1041/action", json={"action": "note", "text": "Called."}, headers=STAFF)
    live.post(url, json={}, headers=STAFF)
    assert len(calls) == 3, "a changed case is planned again"


def test_prep_brief_is_cached_per_case(live, monkeypatch):
    calls = counting(monkeypatch, ba, "advisor_brief", BRIEF)
    for _ in range(2):
        assert live.post("/staff/cases/CASE-1041/brief", headers=STAFF).json()["headline"] == "H"
    live.post("/staff/cases/CASE-1040/brief", headers=STAFF)
    assert len(calls) == 2, "one call per case, not per view"


def test_an_offline_fallback_is_not_cached_so_the_model_is_retried(live, monkeypatch):
    calls = []

    def boom(*args, **kwargs):
        calls.append(args)
        raise RuntimeError("throttled")

    monkeypatch.setattr(aa, "plan_next_steps", boom)
    for _ in range(2):
        assert "offline" in live.post("/staff/cases/CASE-1041/next-steps", json={}, headers=STAFF).json()["note"]
    assert len(calls) == 2
