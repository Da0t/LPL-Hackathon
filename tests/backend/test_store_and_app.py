"""Seed loading, reset, static page serving, settings, and helper endpoints."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.settings import REPO_ROOT, Settings
from backend.store import Store
from tests.backend.conftest import SEED_CASE_IDS, STAFF, make_settings, submit_roth_thing_case


def test_fallback_fixtures_load_when_data_dir_missing(tmp_path):
    settings = make_settings(tmp_path)
    store = Store(":memory:", settings.data_dir, settings.fallback_data_dir)
    assert "fallback" in store.load_seed()
    counts = store.counts()
    assert (counts["clients"], counts["accounts"], counts["events"], counts["advisors"], counts["glossary"], counts["seed_cases"]) == (3, 8, 10, 8, 10, 4)
    account = store.get_account("ACCT-201")
    assert account["masked_identifier"] == "****4821" and account["label"] == "Rollover IRA" and account["balance"] == 84000
    assert store.get_client("CLIENT-022")["meeting_preference"] == "video"
    assert store.glossary_lookup("the Roth thing")["term"] == "Roth IRA", "also_heard_as aliases work"
    assert store.get_advisor("ADV-03")["meeting_mode"] == ["phone", "video"]
    assert store.specialist_queues and store.specialist_queues[0]["destination"] == "security_specialist_review"


def test_fallback_fixtures_match_agent4_data_contract(tmp_path):
    """The fallback copy must keep the frozen fixture's fixed records unchanged."""
    fixture = json.loads((REPO_ROOT / "contracts" / "demo_fixture_v1.json").read_text())
    store = Store(":memory:", tmp_path / "none", REPO_ROOT / "backend" / "fixtures")
    store.load_seed()
    for account in fixture["accounts"]:
        stored = store.get_account(account["account_id"])
        assert stored["client_id"] == account["client_id"] and stored["masked_identifier"] == account["masked_identifier"]
        assert stored["balance"] == account["balance"] and stored["source_id"] == account["source_id"]
    for advisor in fixture["advisors"]:
        assert store.get_advisor(advisor["advisor_id"])["display_name"] == advisor["display_name"]
    assert {c["case_id"] for c in store.list_cases()} >= {c["case_id"] for c in fixture["cases"]}


def test_agent4_data_dir_is_preferred_and_tolerant(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "clients.json").write_text(json.dumps({"meta": {}, "clients": [{"id": "CLIENT-900", "name": "Test Person", "advisor_id": "ADV-900", "contact_preference": "video"}]}))
    (data / "accounts.json").write_text(json.dumps([{"id": "ACCT-900", "owner_client_id": "CLIENT-900", "type": "Roth IRA", "last4": "1234", "balance_snapshot": "12,500", "as_of": "2026-09-30"}]))
    (data / "events.json").write_text(json.dumps([{"source_id": "EVT-1", "account_id": "ACCT-900", "event_type": "contribution", "event_date": "2026-01-02", "summary": "Deposit"}]))
    (data / "advisors.json").write_text(json.dumps([{"id": "ADV-900", "name": "Adv Nine", "specialty_tags": "retirement_income, account_service", "meeting_mode": "video", "capacity": 2, "availability": "available", "status": "active"}]))
    (data / "glossary.json").write_text(json.dumps({"terms": [{"term": "Roth IRA", "definition": "Approved text.", "also_heard_as": ["roth"]}]}))

    store = Store(":memory:", data, make_settings(tmp_path).fallback_data_dir)
    source = store.load_seed()
    assert "fallback" not in source
    account = store.get_account("ACCT-900")
    assert account["account_type"] == "roth_ira" and account["masked_identifier"] == "****1234" and account["balance"] == 12500 and account["label"] == "Roth IRA"
    assert store.events_for_account("ACCT-900")[0]["source_id"] == "EVT-1" and store.events_for_account("ACCT-900")[0]["description"] == "Deposit"
    advisor = store.get_advisor("ADV-900")
    assert advisor["specialties"] == ["retirement_income", "account_service"] and advisor["meeting_mode"] == ["video"] and advisor["active"] is True
    assert store.existing_advisor_id("CLIENT-900") == "ADV-900"
    assert store.glossary_lookup("roth")["plain"] == "Approved text."
    assert store.counts()["seed_cases"] == 0, "cases.json is optional"


def test_incomplete_data_dir_falls_back_entirely(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "clients.json").write_text("[]")
    store = Store(":memory:", data, make_settings(tmp_path).fallback_data_dir)
    assert "fallback" in store.load_seed()


def test_reset_restores_seed_cases_and_numbering(client):
    submit_roth_thing_case(client)
    assert client.post("/demo/reset").status_code == 403
    response = client.post("/demo/reset", headers=STAFF)
    assert response.status_code == 200 and response.json()["status"] == "reset" and response.json()["server_restart_required"] is False
    rows = {c["case_id"]: c for c in client.get("/staff/cases", headers=STAFF).json()["cases"]}
    assert set(rows) == SEED_CASE_IDS, "live cases cleared, seed cases restored"
    assert rows["CASE-1042"]["status"] == "submitted" and rows["CASE-1042"]["routing"]["assigned_advisor_id"] is None
    assert submit_roth_thing_case(client) == "CASE-1043", "numbering restarts after the seeds"


def test_case_ids_are_sequential_and_unique(client):
    assert submit_roth_thing_case(client) == "CASE-1043"
    assert submit_roth_thing_case(client) == "CASE-1044"
    ids = [c["case_id"] for c in client.get("/staff/cases", headers=STAFF).json()["cases"]]
    assert len(ids) == len(set(ids))


def test_health_and_demo_clients(client):
    health = client.get("/health").json()
    assert health["status"] == "ok" and health["ai_mode"] == "mock" and health["live_model"] is False and health["simulated_access_control"] is True
    clients = client.get("/demo/clients").json()["clients"]
    assert {c["client_id"] for c in clients} == {"CLIENT-017", "CLIENT-022", "CLIENT-031"}


def test_frontend_placeholders_then_real_files(tmp_path):
    settings = make_settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        for route in ("/client", "/client/", "/staff", "/staff/"):
            response = client.get(route)
            assert response.status_code == 200 and "not here yet" in response.text, route
        assert client.get("/client/app.js").status_code == 404

        settings.staff_frontend_dir.mkdir()
        (settings.staff_frontend_dir / "index.html").write_text("<h1>Staff UI</h1>")
        (settings.staff_frontend_dir / "fonts").mkdir()
        (settings.staff_frontend_dir / "fonts" / "x.woff2").write_bytes(b"wOF2")
        assert "Staff UI" in client.get("/staff").text, "served without restart"
        font = client.get("/staff/fonts/x.woff2")
        assert font.status_code == 200 and font.headers["content-type"].startswith("font/woff2")
        assert client.get("/staff/../../etc/passwd").status_code == 404
        assert client.get("/staff/%2e%2e/%2e%2e/etc/passwd").status_code == 404
        assert client.get("/").status_code == 200


def test_bedrock_and_stub_modes_fail_fast_without_agent1_module(tmp_path):
    from backend.services.agent_adapter import AdapterUnavailable

    for mode in ("bedrock", "stub"):
        with pytest.raises(AdapterUnavailable):
            create_app(make_settings(tmp_path, ai_mode=mode))


def test_settings_read_runbook_env_names(monkeypatch):
    monkeypatch.setenv("SAMEPAGE_AI_MODE", "bedrock")
    assert Settings().validate().ai_mode == "bedrock"
    monkeypatch.delenv("SAMEPAGE_AI_MODE")
    monkeypatch.setenv("SAMEPAGE_AGENT_MODE", "mock")
    assert Settings().validate().ai_mode == "mock"
    monkeypatch.setenv("SAMEPAGE_AI_MODE", "sideways")
    with pytest.raises(ValueError):
        Settings().validate()


def test_reset_demo_command_clears_live_cases_without_restart(tmp_path, monkeypatch, capsys):
    db = tmp_path / "var" / "samepage.db"
    settings = make_settings(tmp_path, db_path=str(db))
    with TestClient(create_app(settings)) as client:
        submit_roth_thing_case(client)
        monkeypatch.setenv("SAMEPAGE_DB_PATH", str(db))
        monkeypatch.setenv("SAMEPAGE_DATA_DIR", str(settings.data_dir))
        from backend import reset_demo

        reset_demo.main()
        assert "reset complete" in capsys.readouterr().out
        assert {c["case_id"] for c in client.get("/staff/cases", headers=STAFF).json()["cases"]} == SEED_CASE_IDS, "running server sees the reset"


def test_persistent_sqlite_survives_restart(tmp_path):
    settings = make_settings(tmp_path, db_path=str(tmp_path / "var" / "samepage.db"))
    with TestClient(create_app(settings)) as client:
        case_id = submit_roth_thing_case(client)
    with TestClient(create_app(settings)) as client:
        assert client.get(f"/staff/cases/{case_id}", headers=STAFF).status_code == 200
        assert len(client.get("/staff/cases", headers=STAFF).json()["cases"]) == len(SEED_CASE_IDS) + 1, "seed cases are not duplicated on restart"
