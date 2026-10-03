"""Offline authorization, persistence, and seeded-account invariants."""

import base64
import copy
import json
import threading
import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.settings import Settings
from backend.portal.seed import make_profiles
from backend.portal.service import Portal, COOKIE


class Table:
    def __init__(self):
        self.rows = {}

    def get_item(self, Key, **kwargs):
        return (
            {"Item": copy.deepcopy(self.rows.get((Key["pk"], Key["sk"])))}
            if (Key["pk"], Key["sk"]) in self.rows
            else {}
        )

    def put_item(self, Item, ConditionExpression=None, ExpressionAttributeValues=None):
        key = (Item["pk"], Item["sk"])
        old = self.rows.get(key)
        conflict = ConditionExpression == "attribute_not_exists(pk)" and old
        conflict = conflict or (
            ConditionExpression == "revision = :r"
            and (old or {}).get("revision") != ExpressionAttributeValues[":r"]
        )
        if conflict:
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException"}}, "PutItem"
            )
        self.rows[key] = copy.deepcopy(Item)


class Cognito:
    def __init__(self, tokens):
        self.tokens = tokens

    def get_user(self, AccessToken):
        if AccessToken not in self.tokens:
            raise ClientError({"Error": {"Code": "NotAuthorizedException"}}, "GetUser")
        return {"UserAttributes": [{"Name": "sub", "Value": self.tokens[AccessToken]}]}

    def global_sign_out(self, AccessToken):
        self.tokens.pop(AccessToken, None)


def token(
    sub,
    client="portal-app",
    issuer="https://cognito-idp.us-east-1.amazonaws.com/portal-pool",
):
    payload = {"sub": sub, "client_id": client, "iss": issuer, "token_use": "access"}
    return (
        "header."
        + base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        + ".signature"
    )


@pytest.fixture
def setup(tmp_path):
    app = create_app(Settings(db_path=str(tmp_path / "app.db"), ai_mode="mock"))
    p = object.__new__(Portal)
    p.table = Table()
    p.store = app.state.store
    p.config = {
        "region": "us-east-1",
        "user_pool_id": "portal-pool",
        "app_client_id": "portal-app",
    }
    p.failures = {}
    p.lock = threading.Lock()
    profiles = make_profiles()
    tokens = {}
    for i, doc in enumerate(profiles):
        sub = "user-" + str(i)
        tokens[token(sub)] = sub
        p.table.put_item(
            Item={
                "pk": "IDENTITY#" + sub,
                "sk": "IDENTITY",
                "document": json.dumps(
                    {"sub": sub, "role": "client", "client_id": doc["client_id"]}
                ),
            }
        )
        p.table.put_item(
            Item={
                "pk": "CLIENT#" + doc["client_id"],
                "sk": "PROFILE",
                "revision": 1,
                "document": json.dumps(doc),
            }
        )
        p.sync_reference(doc)
    p.cognito = Cognito(tokens)
    app.state.portal = p
    app.state.intake.portal = p
    with TestClient(app) as c:
        yield c, p, profiles


def signin(c, user=0):
    c.cookies.set(COOKIE, token("user-" + str(user)))


def test_seed_reconciles_and_transfers_are_paired():
    profiles = make_profiles()
    assert len(profiles) == 3
    for p in profiles:
        assert len(p["accounts"]) >= 4 and len(p["activity"]) >= 30
        assert "ssn" not in p["profile"] and len(p["profile"]["ssn_last4"]) == 4
        for a in p["accounts"]:
            assert (
                round(
                    sum(h["market_value"] for h in a["holdings"]) + a["cash_balance"], 2
                )
                == a["balance"]
            )
            events = sorted(
                [e for e in p["activity"] if e["account_id"] == a["account_id"]],
                key=lambda e: (e["date"], e["event_id"]),
            )
            assert (
                round(a["opening_value"] + sum(e["value_change"] for e in events), 2)
                == a["balance"]
            )
            assert events[-1]["balance_after"] == a["balance"]
        transfers = [e for e in p["activity"] if e["type"].startswith("transfer_")]
        assert len(transfers) == 2 and sum(e["value_change"] for e in transfers) == 0


def test_auth_required_and_headers_cannot_impersonate(setup):
    c, p, profiles = setup
    for url in ["/portal/me", "/auth/me", "/staff/cases", "/demo/clients"]:
        assert c.get(url, headers={"X-Demo-Role": "staff"}).status_code == 401
    signin(c)
    assert c.get("/portal/me").json()["client_id"] == "CLIENT-017"
    assert c.get("/staff/cases", headers={"X-Demo-Role": "staff"}).status_code == 403
    assert (
        c.post(
            "/intake/start",
            json={"client_id": "CLIENT-022"},
            headers={"X-Demo-Client-Id": "CLIENT-022"},
        ).status_code
        == 403
    )
    assert len(c.get("/demo/clients").json()["clients"]) == 1
    for account in profiles[0]["accounts"]:
        expected = {
            e["event_id"]
            for e in profiles[0]["activity"]
            if e["account_id"] == account["account_id"]
        }
        assert {
            e["event_id"] for e in p.store.events_for_account(account["account_id"])
        } == expected


def test_wrong_pool_and_app_rejected_even_if_cognito_accepts_token(setup):
    c, p, _ = setup
    for t in [
        token("user-0", client="different-app"),
        token("user-0", issuer="https://example.com/other-pool"),
    ]:
        p.cognito.tokens[t] = "user-0"
        c.cookies.set(COOKIE, t)
        assert c.get("/portal/me").status_code == 401


def test_profile_persists_and_conflicting_edits_rejected(setup):
    c, p, profiles = setup
    signin(c)
    profile = copy.deepcopy(profiles[0]["profile"])
    profile["preferred_name"] = "Mara updated"
    body = {"revision": 1, "profile": profile}
    r = c.put("/portal/profile", json=body)
    assert r.status_code == 200, r.text
    assert p.get("CLIENT-017")["profile"]["preferred_name"] == "Mara updated"
    assert p.get("CLIENT-022")["profile"]["preferred_name"] == "Evan"
    assert c.put("/portal/profile", json=body).status_code == 409
    profile["ssn_last4"] = "123456789"
    assert (
        c.put("/portal/profile", json={"revision": 2, "profile": profile}).status_code
        == 422
    )


def test_own_account_history_and_document_only(setup):
    c, p, _ = setup
    signin(c)
    assert (
        c.post(
            "/portal/document",
            json={"words": "help", "summary": "help", "account_id": "ACCT-301"},
        ).status_code
        == 403
    )
    r = c.post(
        "/portal/document",
        json={
            "words": "help",
            "summary": "help",
            "account_id": "ACCT-201",
            "amount": 6000,
        },
    )
    assert r.status_code == 200
    doc = r.json()
    assert doc["account"]["balance"] == 84000
    assert {e["account_id"] for e in doc["history"]} == {"ACCT-201"}
    assert "ssn_last4" not in json.dumps(doc)


def test_history_is_reported_and_does_not_execute_transfers(setup):
    c, p, _ = setup
    signin(c)
    before = p.get("CLIENT-017")
    r = c.post(
        "/portal/activity",
        json={
            "revision": 1,
            "account_id": "ACCT-202",
            "related_account_id": "ACCT-203",
            "date": "2026-01-01",
            "type": "transfer",
            "amount": 300,
            "description": "Prior household transfer",
        },
    )
    assert r.status_code == 200, r.text
    after = r.json()
    assert after["accounts"] == before["accounts"]
    assert len(after["activity"]) == len(before["activity"]) + 2
    assert after["activity"][0]["status"] == "client_reported"
    assert (
        c.post(
            "/portal/activity",
            json={
                "revision": 2,
                "account_id": "ACCT-301",
                "date": "2026-01-01",
                "type": "deposit",
                "amount": 300,
                "description": "foreign",
            },
        ).status_code
        == 403
    )


def test_confirm_snapshot_survives_later_profile_edit_and_archive_retry(setup):
    c, p, _ = setup
    signin(c)
    session = c.post("/intake/start", json={"client_id": "CLIENT-017"}).json()[
        "session_id"
    ]
    assert (
        c.post(
            "/intake/" + session + "/turn",
            json={"text": "Discuss my retirement account", "input_mode": "text"},
        ).status_code
        == 200
    )
    response = c.post(
        "/intake/" + session + "/confirm",
        json={
            "confirmed_plain_language_request": "Discuss using $6000 from my retirement account",
            "selected_account_id": "ACCT-201",
            "amount_requested": 6000,
        },
    )
    assert response.status_code == 200, response.text
    caseid = response.json()["case_id"]
    case = p.store.get_case(caseid)
    assert case["_portal_document"]["account"]["balance"] == 84000
    profile = p.get("CLIENT-017")
    profile["accounts"][0]["balance"] = 99999
    p.save(profile, 1)
    first = c.post("/portal/requests/" + caseid + "/archive").json()
    second = c.post("/portal/requests/" + caseid + "/archive").json()
    assert first == second and first["account"]["balance"] == 84000
    signin(c, 1)
    assert c.post("/portal/requests/" + caseid + "/archive").status_code == 404


def test_csrf_and_logout(setup):
    c, p, _ = setup
    signin(c)
    assert (
        c.post("/auth/logout", headers={"Origin": "https://evil.example"}).status_code
        == 403
    )
    assert (
        c.post("/auth/logout", headers={"Origin": "http://127.0.0.1:3200"}).status_code
        == 200
    )
    assert c.get("/portal/me").status_code == 401


def test_account_creation_edit_validation_and_ownership(setup):
    c, p, profiles = setup
    signin(c)
    from backend.portal.routes import AccountInput

    source = profiles[0]["accounts"][0]
    account = {k: source[k] for k in AccountInput.model_fields if k in source}
    account["last4"] = "1234"
    account["familiar_label"] = "Additional savings"
    account["account_type"] = "savings"
    account["balance"] = 1000
    account["cash_balance"] = 1000
    response = c.post("/portal/accounts", json={"revision": 1, "account": account})
    assert response.status_code == 200, response.text
    created = response.json()["accounts"][-1]
    assert created["source_kind"] == "self_reported" and created["holdings"] == []
    assert created["client_id"] == "CLIENT-017"
    assert len(p.get("CLIENT-022")["accounts"]) == len(profiles[1]["accounts"])
    account["cash_balance"] = 1001
    assert (
        c.put(
            "/portal/accounts/" + created["account_id"],
            json={"revision": 2, "account": account},
        ).status_code
        == 422
    )
    account["cash_balance"] = 999
    assert (
        c.put(
            "/portal/accounts/ACCT-301", json={"revision": 2, "account": account}
        ).status_code
        == 404
    )
    assert (
        c.put(
            "/portal/accounts/" + created["account_id"],
            json={"revision": 2, "account": account},
        ).status_code
        == 200
    )
