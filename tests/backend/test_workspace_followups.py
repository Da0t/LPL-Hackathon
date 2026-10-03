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


PACKET = {"headline": "H", "action_type": "account_service", "prepared_fields": [], "compliance_checks": [],
          "draft_client_message": "Hi.", "draft_advisor_followup": "Call."}


def test_prepared_action_is_cached_until_regenerated(live, monkeypatch):
    calls = counting(monkeypatch, ba, "fulfillment_plan", PACKET)
    url = "/staff/cases/CASE-1041/plan"
    first = live.post(url, headers=STAFF)
    assert first.status_code == 200, "a POST with no body is accepted"
    assert live.post(url, json={}, headers=STAFF).json() == first.json() and len(calls) == 1, "reopening shows the same draft"
    live.post(url, json={"refresh": True}, headers=STAFF)
    assert len(calls) == 2, "Regenerate bypasses the cache"


def test_an_offline_fallback_is_not_cached_so_the_model_is_retried(live, monkeypatch):
    calls = []

    def boom(*args, **kwargs):
        calls.append(args)
        raise RuntimeError("throttled")

    monkeypatch.setattr(aa, "plan_next_steps", boom)
    for _ in range(2):
        assert "offline" in live.post("/staff/cases/CASE-1041/next-steps", json={}, headers=STAFF).json()["note"]
    assert len(calls) == 2


# ------------------------------------------------------------- approving a prepared action sends its message


def approve(client, case_id="CASE-1042", **body):
    return client.post(f"/staff/cases/{case_id}/action", json={"action": "approve", **body}, headers=STAFF)


def test_approving_a_prepared_action_sends_its_message_to_the_client(client):
    draft = client.post("/staff/cases/CASE-1042/plan", headers=STAFF).json()["draft_client_message"]
    response = approve(client, text=draft)
    assert response.status_code == 200, response.text
    event = response.json()["event"]
    assert event["event"] == "action_approved" and event["details"]["text"] == draft
    assert event["details"]["compliance"] == {"verdict": "pass", "override": False}
    assert row(client, "CASE-1042")["lifecycle"] == "awaiting_client"
    request = client.get("/my/requests", headers=MARA).json()["requests"][0]
    assert request["awaiting_reply"] is True and [(m["from"], m["text"]) for m in request["messages"]] == [("advisor", draft)]


def test_prepared_message_asks_the_client_for_what_is_missing(client):
    plan = client.post("/staff/cases/CASE-SEC-1/plan", headers=STAFF).json()
    assert {"label": "Account", "value": ""} in plan["prepared_fields"], "a missing fact is listed, not left out"
    assert "which account" in plan["draft_client_message"]
    assert approve(client, "CASE-SEC-1", text=plan["draft_client_message"]).status_code == 200, "the draft still passes compliance"
    complete = client.post("/staff/cases/CASE-1042/plan", headers=STAFF).json()
    assert all(f["value"] for f in complete["prepared_fields"]) and "which account" not in complete["draft_client_message"]


def test_client_can_answer_an_approved_action(client):
    approve(client, text="Hi Mara, we have prepared your request. When is a good time to talk?")
    assert client.post("/my/requests/CASE-1042/reply", json={"text": "Tomorrow morning."}, headers=MARA).status_code == 200
    assert row(client, "CASE-1042")["priority"]["reason"] == "The client replied"


def test_approval_is_refused_when_the_message_fails_compliance(client):
    response = approve(client, text="Hi Mara, you should take the full amount out now.")
    assert response.status_code == 409 and response.json()["error_code"] == "COMPLIANCE_REVIEW_FAILED"
    assert row(client, "CASE-1042")["lifecycle"] == "new"
    assert client.get("/my/requests", headers=MARA).json()["requests"][0]["messages"] == []


def test_approval_without_a_message_is_only_logged(client):
    response = approve(client)
    assert response.status_code == 200 and "text" not in response.json()["event"]["details"]
    assert row(client, "CASE-1042")["lifecycle"] == "new"
    assert client.get("/my/requests", headers=MARA).json()["requests"][0]["messages"] == []


# ------------------------------------------------------------- edge cases


OK_MESSAGE = "Hi Mara, we have prepared your request. When is a good time to talk?"


def messages(client, headers=MARA):
    return client.get("/my/requests", headers=headers).json()["requests"][0]["messages"]


def test_a_prepared_action_can_only_be_approved_once(client):
    assert approve(client, text=OK_MESSAGE).status_code == 200
    again = approve(client, text=OK_MESSAGE)
    assert again.status_code == 409 and again.json()["error_code"] == "ALREADY_APPROVED"
    assert len(messages(client)) == 1, "a double click must not message the client twice"


def test_a_resolved_request_takes_notes_but_no_further_actions(client):
    client.post("/staff/cases/CASE-1042/action", json={"action": "resolve", "text": "Handled by phone."}, headers=STAFF)
    for body in ({"action": "approve", "text": OK_MESSAGE}, {"action": "clarify", "text": OK_MESSAGE},
                 {"action": "schedule"}, {"action": "claim"}, {"action": "resolve", "text": "Again."}):
        response = client.post("/staff/cases/CASE-1042/action", json=body, headers=STAFF)
        assert response.status_code == 409 and response.json()["error_code"] == "CASE_RESOLVED", body
    assert client.post("/staff/cases/CASE-1042/action", json={"action": "note", "text": "Filed."}, headers=STAFF).status_code == 200
    assert messages(client) == []


def test_resolving_a_request_stops_asking_the_client_for_an_answer(client):
    clarify(client)
    client.post("/staff/cases/CASE-1042/action", json={"action": "resolve", "text": "Client called in."}, headers=STAFF)
    request = client.get("/my/requests", headers=MARA).json()["requests"][0]
    assert request["awaiting_reply"] is False and request["lifecycle"] == "resolved"
    late = client.post("/my/requests/CASE-1042/reply", json={"text": "Thursday."}, headers=MARA)
    assert late.status_code == 409 and late.json()["error_code"] == "NOT_AWAITING_REPLY"


def test_a_security_request_is_escalated_only_once(client):
    assert client.post("/staff/cases/CASE-SEC-1/action", json={"action": "escalate"}, headers=STAFF).status_code == 200
    again = client.post("/staff/cases/CASE-SEC-1/action", json={"action": "escalate"}, headers=STAFF)
    assert again.status_code == 409 and again.json()["error_code"] == "ALREADY_ESCALATED"


def test_malformed_action_bodies_are_refused_not_crashed(client):
    for body, code in (
        ({"action": "approve", "text": 42}, "INVALID_TEXT"),
        ({"action": "note", "text": ["a"]}, "INVALID_TEXT"),
        ({"action": "clarify", "text": "x" * 2001}, "MESSAGE_TOO_LONG"),
        ({"action": "approve", "text": "y" * 2001}, "MESSAGE_TOO_LONG"),
    ):
        response = client.post("/staff/cases/CASE-1042/action", json=body, headers=STAFF)
        assert response.status_code == 400 and response.json()["error_code"] == code, body
    assert clarify(client, compliance="yes").status_code == 200, "a non-object compliance field is ignored"


def test_malformed_client_replies_are_refused_not_crashed(client):
    clarify(client)
    assert client.post("/my/requests/CASE-1042/reply", json={"text": 7}, headers=MARA).json()["error_code"] == "INVALID_TEXT"
    assert client.post("/my/requests/CASE-1042/reply", json={"text": "z" * 2001}, headers=MARA).json()["error_code"] == "MESSAGE_TOO_LONG"
    assert len(messages(client)) == 1


def test_malformed_agent_inputs_are_refused_not_crashed(client):
    assert client.post("/staff/cases/CASE-1042/reply-draft", json={"instruction": 5}, headers=STAFF).json()["error_code"] == "INVALID_TEXT"
    assert client.post("/staff/cases/CASE-1042/compliance-review", json={"draft": {"a": 1}}, headers=STAFF).json()["error_code"] == "INVALID_TEXT"


def test_approval_records_the_flagged_checks_the_advisor_acknowledged(client):
    response = approve(client, text=OK_MESSAGE, acknowledged_flags=["Account match", 9, "x" * 500])
    assert response.json()["event"]["details"]["acknowledged_flags"] == ["Account match"]


def test_messaging_a_client_twice_keeps_both_messages_in_order(client):
    clarify(client)
    approve(client, text=OK_MESSAGE)
    assert [m["text"] for m in messages(client)] == [QUESTION, OK_MESSAGE]


# ------------------------------------------------------------- security review on portal-backed records


@pytest.fixture
def signed_in_staff(tmp_path, monkeypatch):
    """Development sign-in mode: the portal replaces each client's seed history with its own ledger."""
    monkeypatch.delenv("COHERENT_PORTAL_CONFIG", raising=False)
    monkeypatch.setenv("COHERENT_DEV_LOGIN", "1")
    with TestClient(create_app(make_settings(tmp_path))) as test_client:
        assert test_client.post("/auth/login", json={"email": "advisor@example.com", "password": "dev"}).status_code == 200
        yield test_client


def test_security_alert_survives_the_portal_replacing_account_history(signed_in_staff):
    inv = signed_in_staff.post("/staff/cases/CASE-SEC-1/investigation").json()
    assert inv["risk_level"] == "high"
    assert any(t["type"] == "security_alert" and t["source_id"] == "EVENT-24" for t in inv["timeline"])


def test_security_timeline_covers_the_weeks_around_the_report_not_all_history(signed_in_staff):
    timeline = signed_in_staff.post("/staff/cases/CASE-SEC-1/investigation").json()["timeline"]
    assert min(t["date"] for t in timeline) >= "2026-07-04", "90 days before the 2026-10-02 report"
    assert len(timeline) < 30 and timeline[-1]["source_id"] == "CASE-SEC-1"


def test_money_leaving_after_an_alert_is_called_out():
    case = {"original_words": "I don't recognize a sign-in.", "flags": ["possible_unauthorized_access"]}
    timeline = [
        {"date": "2026-10-01", "type": "security_alert", "source_id": "EVENT-1", "account": "Brokerage ****1"},
        {"date": "2026-10-02", "type": "transfer_out", "source_id": "TRANSFER-9", "account": "Brokerage ****1"},
        {"date": "2026-10-02", "type": "transfer_in", "source_id": "TRANSFER-9", "account": "Savings ****2"},
    ]
    reasons = aa.stub_investigate_security(case, timeline)["reasons"]
    assert sum("followed the alert" in r for r in reasons) == 1 and any("TRANSFER-9" in r for r in reasons)
