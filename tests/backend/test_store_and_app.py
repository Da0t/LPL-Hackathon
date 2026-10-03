"""Seed loading, reset, static page serving, and helper endpoints."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from backend.main import create_app
from backend.store import Store
from tests.backend.conftest import CLIENT, STAFF, make_settings, submit_roth_thing_case


def test_fallback_fixtures_load_when_data_dir_missing(tmp_path):
    settings = make_settings(tmp_path)
    store = Store(":memory:", settings.data_dir, settings.fallback_data_dir)
    assert "fallback" in store.load_seed()
    counts = store.counts()
    assert counts["clients"] == 3 and counts["accounts"] == 7 and counts["advisors"] == 8 and counts["glossary"] == 10
    assert store.get_account("ACCT-201")["masked_identifier"] == "****4821"


def test_agent4_data_dir_is_preferred_and_tolerant(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "clients.json").write_text(json.dumps({"clients": [{"id": "CLIENT-900", "name": "Test Person", "advisor_id": "ADV-900", "contact_preference": "video"}]}))
    (data / "accounts.json").write_text(json.dumps([{"id": "ACCT-900", "owner_client_id": "CLIENT-900", "type": "Roth IRA", "name": "Roth IRA", "last4": "1234", "balance_snapshot": "12,500", "as_of": "2026-09-30"}]))
    (data / "events.json").write_text(json.dumps([{"id": "EVT-1", "account_id": "ACCT-900", "event_type": "contribution", "event_date": "2026-01-02", "summary": "Deposit"}]))
    (data / "advisors.json").write_text(json.dumps([{"id": "ADV-900", "name": "Adv Nine", "specialty_tags": "retirement_income, account_service", "meeting_mode": "video", "capacity": 2, "availability": "available", "status": "active", "existing_clients": ["CLIENT-900"]}]))
    (data / "glossary.json").write_text(json.dumps({"terms": [{"term": "Roth IRA", "definition": "Approved text.", "synonyms": ["roth"]}]}))

    store = Store(":memory:", data, make_settings(tmp_path).fallback_data_dir)
    source = store.load_seed()
    assert str(data) in source and "fallback" not in source
    account = store.get_account("ACCT-900")
    assert account["account_type"] == "roth_ira" and account["masked_identifier"] == "****1234" and account["balance"] == 12500.0
    assert store.events_for_account("ACCT-900")[0]["source_id"] == "EVT-1"
    advisor = store.get_advisor("ADV-900")
    assert advisor["specialties"] == ["retirement_income", "account_service"] and advisor["meeting_modes"] == ["video"] and advisor["active"] is True
    assert store.existing_advisor_id("CLIENT-900") == "ADV-900"
    assert store.glossary_lookup("roth")["plain"] == "Approved text."


def test_incomplete_data_dir_falls_back_entirely(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "clients.json").write_text("[]")
    store = Store(":memory:", data, make_settings(tmp_path).fallback_data_dir)
    assert "fallback" in store.load_seed()


def test_reset_clears_cases_and_requires_staff(client):
    submit_roth_thing_case(client)
    assert client.get("/staff/cases", headers=STAFF).json()["cases"]
    assert client.post("/demo/reset").status_code == 403
    response = client.post("/demo/reset", headers=STAFF)
    assert response.status_code == 200 and response.json()["status"] == "reset"
    assert client.get("/staff/cases", headers=STAFF).json()["cases"] == []
    assert client.get("/health").json()["counts"]["clients"] == 3
    # Case numbering restarts at the spec example after a reset.
    assert submit_roth_thing_case(client) == "CASE-1042"


def test_case_ids_are_sequential(client):
    assert submit_roth_thing_case(client) == "CASE-1042"
    assert submit_roth_thing_case(client) == "CASE-1043"


def test_health_and_demo_clients(client):
    health = client.get("/health").json()
    assert health["status"] == "ok" and health["agent_mode"] == "mock" and health["simulated_access_control"] is True
    clients = client.get("/demo/clients").json()["clients"]
    assert {c["client_id"] for c in clients} == {"CLIENT-017", "CLIENT-022", "CLIENT-031"}


def test_frontend_placeholders_then_real_files(tmp_path):
    settings = make_settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        for route in ("/client", "/client/", "/staff", "/staff/"):
            response = client.get(route)
            assert response.status_code == 200 and "not here yet" in response.text, route
        assert client.get("/client/app.js").status_code == 404

        settings.client_frontend_dir.mkdir()
        (settings.client_frontend_dir / "index.html").write_text("<h1>Client UI</h1>")
        (settings.client_frontend_dir / "app.js").write_text("console.log('hi')")
        assert "Client UI" in client.get("/client").text, "served without restart"
        js = client.get("/client/app.js")
        assert js.status_code == 200 and "javascript" in js.headers["content-type"]
        assert client.get("/client/../../etc/passwd").status_code == 404
        assert client.get("/client/%2e%2e/%2e%2e/etc/passwd").status_code == 404
        assert client.get("/").status_code == 200


def test_bedrock_mode_fails_fast_without_adapter(tmp_path):
    import pytest

    from backend.services.agent_adapter import AdapterUnavailable

    with pytest.raises(AdapterUnavailable):
        create_app(make_settings(tmp_path, agent_mode="bedrock"))


def test_persistent_sqlite_survives_restart(tmp_path):
    settings = make_settings(tmp_path, db_path=str(tmp_path / "var" / "samepage.db"))
    with TestClient(create_app(settings)) as client:
        case_id = submit_roth_thing_case(client)
    with TestClient(create_app(settings)) as client:
        assert client.get(f"/staff/cases/{case_id}", headers=STAFF).status_code == 200
