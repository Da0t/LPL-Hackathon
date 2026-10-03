"""Tests for intake_turn: tool-loop orchestration, no invented accounts, stub mode."""

from __future__ import annotations

from dataclasses import replace

import pytest

from backend.aws import bedrock_agent as ba
from backend.aws.config import load_config
from tests.aws.fake_bedrock import FakeBedrockClient, tool_use, guardrail_stop
from tests.aws.fixtures import FixtureTools

# Fast, deterministic config: live bedrock mode but no pacing, a model id set.
CFG = replace(
    load_config(),
    ai_mode="bedrock",
    model_id="test-model",
    min_interval_seconds=0.0,
    max_retries=1,
)

ROTH_PHRASE = "I need six thousand dollars from the Roth thing from my old job."


def test_roth_mismatch_asks_instead_of_inventing():
    """Model reads accounts, finds no Roth, asks about the rollover IRA."""
    tools = FixtureTools()
    client = FakeBedrockClient([
        tool_use("t1", "list_my_accounts", {"phrase": ROTH_PHRASE}),
        tool_use("t2", "explain_term", {"term": "rollover IRA"}),
        tool_use("t3", "submit_intake", {
            "suggestions": [
                {"id": "ACCT-201", "label": "Retirement account from former employer", "account_id": "ACCT-201"}
            ],
            "question": "I don't see a Roth IRA here. Could you mean your rollover IRA from your former employer?",
            "definitions": [{"term": "rollover IRA", "plain": "A retirement account that holds money moved from an earlier workplace retirement plan."}],
            "candidate_intent": "discuss_possible_withdrawal",
            "selected_account_id": None,
            "uncertainty": "Client said Roth IRA; the authorized account list shows a rollover IRA instead.",
        }),
    ])

    result = ba.intake_turn("CLIENT-017", ROTH_PHRASE, None, tools, cfg=CFG, client=client)

    assert result["selected_account_id"] is None
    assert "Roth IRA" in result["question"]
    assert result["candidate_intent"] == "discuss_possible_withdrawal"
    assert result["uncertainty"]
    # Only real accounts survive; no invented Roth account.
    assert [s["account_id"] for s in result["suggestions"]] == ["ACCT-201"]
    assert result["definitions"][0]["term"] == "rollover IRA"


def test_invented_account_is_dropped():
    """A suggestion for an account the client does not own is filtered out."""
    tools = FixtureTools()
    client = FakeBedrockClient([
        tool_use("t1", "list_my_accounts", {"phrase": ROTH_PHRASE}),
        tool_use("t2", "submit_intake", {
            "suggestions": [
                {"id": "ACCT-999", "label": "A Roth IRA I made up", "account_id": "ACCT-999"},
                {"id": "ACCT-201", "label": "Real rollover IRA", "account_id": "ACCT-201"},
            ],
            "question": None,
            "definitions": [],
            "candidate_intent": "account_service",
            "selected_account_id": "ACCT-999",
            "uncertainty": None,
        }),
    ])

    result = ba.intake_turn("CLIENT-017", ROTH_PHRASE, None, tools, cfg=CFG, client=client)
    ids = [s["account_id"] for s in result["suggestions"]]
    assert "ACCT-999" not in ids
    assert ids == ["ACCT-201"]
    # Invented selected account is rejected too.
    assert result["selected_account_id"] is None


def test_tool_loop_feeds_results_back_to_model():
    """The loop should send a toolResult user message after a read tool call."""
    tools = FixtureTools()
    client = FakeBedrockClient([
        tool_use("t1", "list_my_accounts", {"phrase": ROTH_PHRASE}),
        tool_use("t2", "submit_intake", {
            "suggestions": [], "question": "Which account?", "definitions": [],
            "candidate_intent": None, "selected_account_id": None, "uncertainty": None,
        }),
    ])
    ba.intake_turn("CLIENT-017", ROTH_PHRASE, None, tools, cfg=CFG, client=client)

    # Second converse call must include a toolResult carrying the account list.
    second_messages = client.calls[1]["messages"]
    tool_result_blocks = [
        b for m in second_messages for b in m.get("content", []) if "toolResult" in b
    ]
    assert tool_result_blocks, "expected a toolResult fed back to the model"
    payload = tool_result_blocks[0]["toolResult"]["content"][0]["json"]["result"]
    assert any(a["account_id"] == "ACCT-201" for a in payload)


def test_guardrail_block_raises_adapter_error():
    tools = FixtureTools()
    client = FakeBedrockClient([guardrail_stop()])
    with pytest.raises(ba.BedrockAdapterError) as exc:
        ba.intake_turn("CLIENT-017", ROTH_PHRASE, None, tools, cfg=CFG, client=client)
    assert exc.value.code == "GUARDRAIL_BLOCKED"


def test_stub_mode_roth_mismatch():
    """Offline stub path reproduces the mismatch behavior with no bedrock client."""
    stub_cfg = replace(CFG, ai_mode="stub")
    tools = FixtureTools()
    result = ba.intake_turn("CLIENT-017", ROTH_PHRASE, None, tools, cfg=stub_cfg)
    assert "Roth IRA" in result["question"]
    assert result["selected_account_id"] is None
    assert result["uncertainty"]
