"""Tests for triage_case: taxonomy validation, fraud safety net, stub mode."""

from __future__ import annotations

from dataclasses import replace

from backend.aws import bedrock_agent as ba
from backend.aws.config import load_config
from tests.aws.fake_bedrock import FakeBedrockClient, tool_use
from tests.aws.fixtures import FixtureTools

CFG = replace(
    load_config(), ai_mode="bedrock", model_id="test-model",
    min_interval_seconds=0.0, max_retries=1,
)


def test_triage_normal_case_categories():
    tools = FixtureTools()
    client = FakeBedrockClient([
        tool_use("t1", "submit_triage", {
            "client_summary": "We'll have an advisor follow up about your retirement account.",
            "staff_summary": "Client requests discussion of a possible $6,000 distribution from a rollover IRA.",
            "intent": "discuss_possible_withdrawal",
            "categories": ["withdrawal_or_distribution", "retirement_income"],
            "unresolved_questions": ["Desired timing"],
            "flags": ["client_term_did_not_match_account_type"],
            "recommended_advisor_ids": ["ADV-03"],
            "routing_hint": "retirement_advisor_review",
        }),
    ])
    confirmed = {
        "confirmed_plain_language_request": "Use $6,000 from my former-employer retirement account.",
        "selected_account_id": "ACCT-201",
        "amount_requested": 6000,
    }
    result = ba.triage_case(confirmed, tools, cfg=CFG, client=client)
    assert set(result["categories"]) == {"withdrawal_or_distribution", "retirement_income"}
    assert result["recommended_advisor_ids"] == ["ADV-03"]
    assert result["routing_hint"] == "retirement_advisor_review"


def test_unknown_category_is_filtered():
    tools = FixtureTools()
    client = FakeBedrockClient([
        tool_use("t1", "submit_triage", {
            "client_summary": "ok", "staff_summary": "ok", "intent": "x",
            "categories": ["made_up_category"],  # not in taxonomy
            "unresolved_questions": [], "flags": [],
        }),
    ])
    result = ba.triage_case({"confirmed_plain_language_request": "hello"}, tools, cfg=CFG, client=client)
    # Falls back to a valid taxonomy value instead of emitting the bad one.
    assert result["categories"] == ["other_or_unclear"]


def test_fraud_safety_net_never_recommends_general_advisor():
    tools = FixtureTools()
    # Model (incorrectly) tries to recommend a general advisor on a security case.
    client = FakeBedrockClient([
        tool_use("t1", "submit_triage", {
            "client_summary": "We'll review the sign-in you don't recognize.",
            "staff_summary": "Possible unauthorized sign-in; requests access review.",
            "intent": "review_account_access",
            "categories": ["fraud_or_security", "account_service"],
            "unresolved_questions": ["Time and device of the alert"],
            "flags": [],
            "recommended_advisor_ids": ["ADV-03"],
            "routing_hint": "retirement_advisor_review",
        }),
    ])
    confirmed = {"confirmed_plain_language_request": "I don't recognize a sign-in on my account."}
    result = ba.triage_case(confirmed, tools, cfg=CFG, client=client)
    assert "fraud_or_security" in result["categories"]
    assert result["routing_hint"] == "security_specialist_review"
    assert result["recommended_advisor_ids"] == []
    assert "possible_unauthorized_access" in result["flags"]


def test_stub_triage_security_routing():
    stub_cfg = replace(CFG, ai_mode="stub")
    tools = FixtureTools()
    confirmed = {"confirmed_plain_language_request": "I need help reviewing an account sign-in I do not recognize."}
    result = ba.triage_case(confirmed, tools, cfg=stub_cfg)
    assert result["routing_hint"] == "security_specialist_review"
    assert result["recommended_advisor_ids"] == []
