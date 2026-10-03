"""Tests for the advisor-workspace agents: reply drafter and compliance reviewer."""

from __future__ import annotations

from dataclasses import replace

from backend.aws import advisor_agents as aa
from backend.aws.config import load_config
from tests.aws.fake_bedrock import FakeBedrockClient, tool_use

CFG = replace(
    load_config(), ai_mode="bedrock", model_id="test-model",
    min_interval_seconds=0.0, max_retries=1,
)
STUB = replace(CFG, ai_mode="stub")

CASE = {
    "case_id": "CASE-T",
    "client_display_name": "Mara Ellis",
    "confirmed_plain_language_request": "I want to speak with an advisor about using $6,000 from my retirement account.",
    "categories": ["withdrawal_or_distribution"],
    "flags": [],
    "unresolved_questions": ["Desired timing", "Potential tax implications for advisor review"],
    "account_context": {"account_type": "rollover_ira", "masked_identifier": "****4821", "account_source_id": "ACCT-201"},
    "history": [],
}


# ------------------------------------------------------------- offline fallbacks


def test_stub_draft_greets_the_client_and_asks_only_client_facing_questions():
    message = aa.draft_reply(CASE, None, cfg=STUB)["message"]
    assert message.startswith("Hi Mara,")
    assert "desired timing" in message.lower()
    assert "advisor review" not in message.lower(), "internal review items are not questions for the client"


def test_stub_draft_carries_the_advisors_instruction_addressed_to_the_client():
    message = aa.draft_reply(CASE, "Tell her she should move it into a Roth IRA.", cfg=STUB)["message"]
    assert "you should move it into a Roth IRA." in message


def test_stub_revision_drops_the_flagged_sentence():
    first = aa.draft_reply(CASE, "Tell her she should move it into a Roth IRA.", cfg=STUB)["message"]
    findings = aa.compliance_review(CASE, first, cfg=STUB)["findings"]
    assert findings, "the first draft must be flagged for this test to mean anything"
    revised = aa.draft_reply(CASE, "Tell her she should move it into a Roth IRA.", findings, first, cfg=STUB)["message"]
    assert "should" not in revised.lower() and revised.startswith("Hi Mara,")
    assert aa.compliance_review(CASE, revised, cfg=STUB)["verdict"] == "pass"


def test_stub_review_quotes_each_advice_phrase_in_a_draft():
    review = aa.compliance_review(CASE, "I recommend the Roth. It is guaranteed to grow.", cfg=STUB)
    assert review["verdict"] == "needs_changes"
    assert {f["quote"].lower() for f in review["findings"]} == {"i recommend", "guaranteed"}
    assert all(f["issue"] and f["suggestion"] for f in review["findings"])


def test_stub_review_of_the_case_record_reads_advisor_notes_and_flags():
    case = dict(CASE, flags=["client_term_did_not_match_account_type"], history=[
        {"event": "advisor_note", "at": "2026-10-01T00:00:00Z", "details": {"text": "Told client you should sell everything."}}])
    checks = {c["id"]: c for c in aa.compliance_review(case, cfg=STUB)["checks"]}
    assert checks["no_advice"]["status"] == "attention" and "you should" in checks["no_advice"]["evidence"].lower()
    assert checks["account_confirmed"]["status"] == "attention"
    assert checks["suitability"]["status"] == "attention" and "Desired timing" in checks["suitability"]["evidence"]
    assert checks["identity_confirmed"]["status"] == "attention"


def test_stub_review_passes_account_check_when_the_record_backs_it():
    checks = {c["id"]: c for c in aa.compliance_review(CASE, cfg=STUB)["checks"]}
    assert checks["account_confirmed"]["status"] == "pass" and "****4821" in checks["account_confirmed"]["evidence"]


# ------------------------------------------------------------- live path (scripted Bedrock)


def test_bedrock_draft_sends_findings_and_previous_draft_on_revision():
    client = FakeBedrockClient([tool_use("t1", "submit_draft", {"message": "  Hi Mara, when works for you?  "})])
    findings = [{"quote": "you should", "issue": "advice", "suggestion": "remove"}]
    result = aa.draft_reply(CASE, "ask about timing", findings, "You should wait.", cfg=CFG, client=client)
    assert result == {"message": "Hi Mara, when works for you?"}
    sent = client.calls[0]["messages"][0]["content"][0]["text"]
    assert "ask about timing" in sent and "You should wait." in sent and "you should" in sent


def test_bedrock_review_is_normalized_to_all_four_checks_and_a_computed_verdict():
    client = FakeBedrockClient([tool_use("t1", "submit_review", {
        "verdict": "pass",  # the model's own verdict is ignored; findings decide
        "checks": [{"id": "no_advice", "status": "attention", "evidence": "Draft recommends a product."},
                   {"id": "made_up_check", "status": "pass", "evidence": "x"}],
        "findings": [{"quote": "best option", "issue": "Recommendation.", "suggestion": "Describe, don't recommend."}],
    })])
    review = aa.compliance_review(CASE, "The Roth is your best option.", cfg=CFG, client=client)
    assert [c["id"] for c in review["checks"]] == ["identity_confirmed", "no_advice", "suitability", "account_confirmed"]
    assert review["checks"][1] == {"id": "no_advice", "label": "No investment / tax advice given",
                                   "status": "attention", "evidence": "Draft recommends a product."}
    assert review["checks"][0]["status"] == "attention", "a check the model skipped is never reported as passed"
    assert review["verdict"] == "needs_changes"
    assert "The Roth is your best option." in client.calls[0]["messages"][0]["content"][0]["text"]


# ------------------------------------------------------------- next-steps planner + fraud investigator


def test_bedrock_plan_is_normalized_to_known_owners_and_real_steps():
    client = FakeBedrockClient([tool_use("t1", "submit_plan", {
        "summary": " Confirm the account, then prepare the paperwork. ",
        "steps": [{"title": "Confirm the account", "detail": "Record shows a rollover IRA.", "owner": "advisor"},
                  {"title": "Send the form", "detail": "Distribution form.", "owner": "back office"},
                  {"title": "  ", "detail": "no title", "owner": "client"}],
    })])
    plan = aa.plan_next_steps(CASE, cfg=CFG, client=client)
    assert plan["summary"] == "Confirm the account, then prepare the paperwork."
    assert [(s["title"], s["owner"]) for s in plan["steps"]] == [("Confirm the account", "advisor"), ("Send the form", "advisor")]


def test_bedrock_investigation_keeps_only_a_known_risk_level_and_sees_the_timeline():
    timeline = [{"date": "2026-10-02", "label": "Security alert", "detail": "New device", "account": "Brokerage ****1187",
                 "source_id": "EVENT-24", "highlight": True}]
    client = FakeBedrockClient([tool_use("t1", "submit_investigation", {
        "risk_level": "catastrophic", "reasons": ["New device sign-in (EVENT-24)."], "recommended_steps": ["Verify identity."]})])
    result = aa.investigate_security(CASE, timeline, cfg=CFG, client=client)
    assert result == {"risk_level": "medium", "reasons": ["New device sign-in (EVENT-24)."], "recommended_steps": ["Verify identity."]}
    assert "EVENT-24" in client.calls[0]["messages"][0]["content"][0]["text"]


def test_stub_investigation_is_medium_risk_without_an_alert_on_record():
    case = dict(CASE, flags=["possible_unauthorized_access"], categories=["fraud_or_security"])
    result = aa.investigate_security(case, [], cfg=STUB)
    assert result["risk_level"] == "medium" and result["reasons"]
