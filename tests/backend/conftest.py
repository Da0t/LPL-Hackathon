"""Shared fixtures for backend tests. Everything runs offline against the mock adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.services.agent_adapter import AgentAdapter
from backend.settings import REPO_ROOT, Settings

STAFF = {"X-Demo-Role": "staff"}
CLIENT = {"X-Demo-Role": "client"}

ROTH_THING = "I need six thousand dollars for my husband's care. It's in the Roth thing from my old job."
CLEAR_ROTH = "I have a question about my Roth IRA. Can I still contribute this year?"
BENEFICIARY = "I want to change who gets my IRA when I die. My daughter should be on it."
SECURITY = "Someone moved money out of my brokerage account and I didn't do it."


def make_settings(tmp_path: Path, **overrides: Any) -> Settings:
    base = dict(
        agent_mode="mock",
        db_path=":memory:",
        data_dir=tmp_path / "no-such-data-dir",
        fallback_data_dir=REPO_ROOT / "backend" / "fixtures",
        default_demo_role="client",
        adapter_timeout_s=5.0,
        client_frontend_dir=tmp_path / "frontend-client",
        staff_frontend_dir=tmp_path / "frontend-staff",
        reset_on_start=False,
    )
    base.update(overrides)
    return Settings(**base)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def app(settings: Settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


def make_client_with_adapter(tmp_path: Path, intake_fn, triage_fn) -> TestClient:
    adapter = AgentAdapter(intake_fn, triage_fn, timeout_s=2.0)
    adapter.name = "test-adapter"
    app = create_app(make_settings(tmp_path), adapter=adapter)
    return TestClient(app)


# ------------------------------------------------------------- helpers


def start(client: TestClient, client_id: str = "CLIENT-017") -> str:
    response = client.post("/intake/start", json={"client_id": client_id}, headers=CLIENT)
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


def turn(client: TestClient, session_id: str, text: str = "", option: str | None = None, mode: str = "text") -> dict[str, Any]:
    payload: dict[str, Any] = {"text": text, "input_mode": mode}
    if option:
        payload["selected_option_id"] = option
    response = client.post(f"/intake/{session_id}/turn", json=payload, headers=CLIENT)
    assert response.status_code == 200, response.text
    return response.json()


def confirm(client: TestClient, session_id: str, wording: str, account_id: str | None = None, amount: float | None = None, expect: int = 200) -> dict[str, Any]:
    payload: dict[str, Any] = {"confirmed_plain_language_request": wording}
    if account_id is not None:
        payload["selected_account_id"] = account_id
    if amount is not None:
        payload["amount_requested"] = amount
    response = client.post(f"/intake/{session_id}/confirm", json=payload, headers=CLIENT)
    assert response.status_code == expect, response.text
    return response.json()


def submit_roth_thing_case(client: TestClient) -> str:
    """Run the demo scenario through to a submitted case; return case_id."""
    sid = start(client, "CLIENT-017")
    first = turn(client, sid, ROTH_THING, mode="voice")
    yes = next(s for s in first["suggestions"] if s["account_id"] == "ACCT-201")
    second = turn(client, sid, option=yes["id"])
    withdraw = next(s for s in second["suggestions"] if s["id"] == "opt-withdraw")
    third = turn(client, sid, option=withdraw["id"])
    result = confirm(client, sid, third["proposed_plain_language_request"], "ACCT-201", 6000)
    return result["case_id"]
