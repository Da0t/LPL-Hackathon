"""Drafter + compliance-reviewer loop: orchestration, and the staff endpoints that expose it."""

from __future__ import annotations

from backend.services.reply_workflow import run_reply_workflow
from tests.backend.conftest import STAFF

CASE = {"case_id": "CASE-T", "client_display_name": "Mara Ellis"}
PASS = {"verdict": "pass", "checks": [], "findings": []}
FLAG = {"verdict": "needs_changes", "checks": [],
        "findings": [{"quote": "you should", "issue": "Reads as a recommendation.", "suggestion": "Remove it."}]}


class Agents:
    """Scripted drafter/reviewer that record what the orchestrator handed them."""

    def __init__(self, drafts: list[str], reviews: list[dict]):
        self.drafts, self.reviews = list(drafts), list(reviews)
        self.draft_calls: list[dict] = []
        self.review_calls: list[str] = []

    def draft(self, case, instruction, findings=None, previous=None):
        self.draft_calls.append({"instruction": instruction, "findings": findings, "previous": previous})
        return {"message": self.drafts.pop(0)}

    def review(self, case, draft=None):
        self.review_calls.append(draft)
        return self.reviews.pop(0)


def test_clean_draft_passes_without_revision():
    agents = Agents(["Hello Mara."], [PASS])
    result = run_reply_workflow(CASE, "ask about timing", agents.draft, agents.review)
    assert result["draft"] == "Hello Mara."
    assert result["review"]["verdict"] == "pass" and result["revised"] is False
    assert [(t["agent"], t["step"]) for t in result["trace"]] == [("drafter", "draft"), ("compliance", "review")]
    assert agents.draft_calls[0]["instruction"] == "ask about timing"


def test_flagged_draft_is_revised_once_with_the_reviewers_findings():
    agents = Agents(["You should move it.", "Your advisor will go over the options."], [FLAG, PASS])
    result = run_reply_workflow(CASE, None, agents.draft, agents.review)
    assert result["draft"] == "Your advisor will go over the options."
    assert result["revised"] is True and result["review"]["verdict"] == "pass"
    assert agents.draft_calls[1]["findings"] == FLAG["findings"]
    assert agents.draft_calls[1]["previous"] == "You should move it."
    assert agents.review_calls == ["You should move it.", "Your advisor will go over the options."]
    assert [(t["agent"], t["step"]) for t in result["trace"]] == [
        ("drafter", "draft"), ("compliance", "review"), ("drafter", "revise"), ("compliance", "review")]


def test_draft_still_flagged_after_one_revision_is_returned_as_needs_changes():
    agents = Agents(["You should a.", "You should b."], [FLAG, FLAG])
    result = run_reply_workflow(CASE, None, agents.draft, agents.review)
    assert result["draft"] == "You should b." and result["revised"] is True
    assert result["review"]["verdict"] == "needs_changes"
    assert len(agents.draft_calls) == 2, "the loop revises at most once"


# ------------------------------------------------------------- endpoints (mock mode)


def test_reply_draft_endpoint_returns_a_passing_draft_and_saves_nothing(client):
    before = client.get("/staff/cases/CASE-1042", headers=STAFF).json()
    response = client.post("/staff/cases/CASE-1042/reply-draft", json={}, headers=STAFF)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["case_id"] == "CASE-1042" and body["ai_mode"] == "mock"
    assert "Mara" in body["draft"]
    assert body["review"]["verdict"] == "pass" and body["revised"] is False
    assert {c["id"] for c in body["review"]["checks"]} == {"identity_confirmed", "no_advice", "suitability", "account_confirmed"}
    after = client.get("/staff/cases/CASE-1042", headers=STAFF).json()
    assert after["history"] == before["history"] and after["status"] == before["status"]


def test_reply_draft_endpoint_revises_when_the_instruction_asks_for_advice(client):
    response = client.post("/staff/cases/CASE-1042/reply-draft",
                           json={"instruction": "Tell her she should move it all into a Roth IRA."}, headers=STAFF)
    body = response.json()
    assert body["revised"] is True and body["review"]["verdict"] == "pass"
    assert "should" not in body["draft"].lower()
    assert [t["step"] for t in body["trace"]] == ["draft", "review", "revise", "review"]


def test_compliance_review_endpoint_flags_advice_in_an_edited_draft(client):
    response = client.post("/staff/cases/CASE-1042/compliance-review",
                           json={"draft": "Hi Mara, I recommend you withdraw the full amount."}, headers=STAFF)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["verdict"] == "needs_changes"
    assert any("recommend" in f["quote"].lower() for f in body["findings"])


def test_compliance_review_endpoint_without_a_draft_reviews_the_case_record(client):
    body = client.post("/staff/cases/CASE-1042/compliance-review", json={}, headers=STAFF).json()
    checks = {c["id"]: c for c in body["checks"]}
    assert checks["account_confirmed"]["status"] == "attention", "the term-mismatch flag on CASE-1042 needs resolving"
    assert checks["no_advice"]["status"] == "pass"
    assert body["findings"] == [] and body["verdict"] == "needs_changes"
    assert all(c["evidence"] for c in body["checks"])


def test_agent_endpoints_require_staff_and_a_real_case(client):
    assert client.post("/staff/cases/CASE-1042/reply-draft", json={}, headers={"X-Demo-Role": "client", "X-Demo-Client-Id": "CLIENT-017"}).status_code == 403
    assert client.post("/staff/cases/NOPE/reply-draft", json={}, headers=STAFF).status_code == 404
    assert client.post("/staff/cases/NOPE/compliance-review", json={}, headers=STAFF).status_code == 404


def test_reply_draft_falls_back_to_offline_agents_when_the_live_model_fails(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from backend.aws import advisor_agents as aa
    from backend.main import create_app
    from backend.services.agent_adapter import MockAdapter
    from tests.backend.conftest import make_settings

    def boom(*_args, **_kwargs):
        raise RuntimeError("no credentials")

    monkeypatch.setattr(aa, "draft_reply", boom)
    monkeypatch.setattr(aa, "compliance_review", boom)
    adapter = MockAdapter()
    adapter.live = True  # create_app refuses a non-live adapter in bedrock mode
    app = create_app(make_settings(tmp_path, ai_mode="bedrock"), adapter=adapter)
    with TestClient(app) as live:
        draft = live.post("/staff/cases/CASE-1042/reply-draft", json={}, headers=STAFF).json()
        review = live.post("/staff/cases/CASE-1042/compliance-review", json={}, headers=STAFF).json()
    assert "Mara" in draft["draft"] and "offline" in draft["note"]
    assert len(review["checks"]) == 4 and "offline" in review["note"]
