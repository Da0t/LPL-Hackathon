"""Authenticated portal APIs. No client identifier from the browser is trusted."""

import secrets
from datetime import date
from typing import Literal
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field, ConfigDict
from backend.errors import ApiError
from backend.portal.service import COOKIE

router = APIRouter()


def portal(request):
    service = getattr(request.app.state, "portal", None)
    if not service:
        raise ApiError(
            503,
            "PORTAL_NOT_CONFIGURED",
            "Client sign-in is not configured on this server.",
        )
    return service


def own(request):
    p = portal(request)
    actor = p.actor(request)
    if actor["role"] != "client":
        raise ApiError(
            403, "CLIENT_REQUIRED", "Use a client account for this workspace."
        )
    return p, actor["client_id"]


class Login(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


@router.post("/auth/login")
def login(body: Login, request: Request, response: Response):
    auth = portal(request).login(body.email, body.password, request.client.host)
    response.set_cookie(
        COOKIE,
        auth["AccessToken"],
        max_age=auth["ExpiresIn"],
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return {"signed_in": True}


@router.post("/auth/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE)
    if token:
        try:
            portal(request).cognito.global_sign_out(AccessToken=token)
        except Exception:
            pass
    response.delete_cookie(COOKIE, path="/")
    return {"signed_out": True}


@router.get("/auth/me")
def me(request: Request):
    return portal(request).actor(request)


@router.get("/portal/me")
def workspace(request: Request):
    p, cid = own(request)
    return p.get(cid)


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid", str_max_length=500)
    legal_name: str = Field(min_length=2, max_length=120)
    preferred_name: str = ""
    date_of_birth: date
    ssn_last4: str = Field(pattern=r"^\d{4}$")
    phone: str = ""
    email: str = Field(max_length=254)
    street: str = ""
    address_line2: str = ""
    city: str = ""
    state: str = Field(max_length=2)
    postal_code: str = Field(max_length=12)
    country: str = "United States"
    citizenship: str = "United States"
    tax_residency: str = "United States"
    marital_status: str = ""
    employment_status: str = ""
    employer: str = ""
    occupation: str = ""
    trusted_contact: str = ""
    trusted_contact_relationship: str = ""
    trusted_contact_phone: str = ""
    preferred_contact: str = "email"
    meeting_preference: str = "video"
    annual_income: float = Field(ge=0, le=1e12, allow_inf_nan=False)
    net_worth: float = Field(ge=0, le=1e12, allow_inf_nan=False)
    liquid_net_worth: float = Field(ge=0, le=1e12, allow_inf_nan=False)
    monthly_expenses: float = Field(ge=0, le=1e12, allow_inf_nan=False)
    liabilities: float = Field(ge=0, le=1e12, allow_inf_nan=False)
    investment_objective: str = ""
    risk_tolerance: str = ""
    time_horizon: str = ""
    investment_experience: str = ""
    liquidity_needs: str = ""
    retirement_age: int = Field(ge=18, le=100)
    emergency_fund_months: int = Field(ge=0, le=120)
    tax_filing_status: str = ""
    notes: str = ""


class ProfileUpdate(BaseModel):
    revision: int = Field(ge=1)
    profile: Profile


@router.put("/portal/profile")
def update_profile(body: ProfileUpdate, request: Request):
    p, cid = own(request)
    doc = p.get(cid)
    if body.profile.date_of_birth >= date.today():
        raise ApiError(422, "INVALID_BIRTH_DATE", "Date of birth must be in the past.")
    doc["profile"] = body.profile.model_dump(mode="json")
    doc["display_name"] = body.profile.legal_name
    return p.save(doc, body.revision)


ACCOUNT_TYPES = [
    "brokerage",
    "joint_brokerage",
    "roth_ira",
    "traditional_ira",
    "rollover_ira",
    "401k",
    "403b",
    "457b",
    "sep_ira",
    "simple_ira",
    "hsa",
    "529",
    "trust",
    "cash_management",
    "savings",
    "cd",
]


class AccountInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_max_length=300)
    familiar_label: str = Field(min_length=2, max_length=120)
    account_type: str
    last4: str = Field(pattern=r"^\d{4}$")
    custodian: str = Field(min_length=2)
    ownership: str = "individual"
    balance: float = Field(ge=0, le=1e12, allow_inf_nan=False)
    cash_balance: float = Field(ge=0, le=1e12, allow_inf_nan=False)
    cost_basis: float = Field(ge=0, le=1e12, allow_inf_nan=False)
    balance_as_of: date
    opened_date: date
    contributions_ytd: float = Field(default=0, ge=0, le=1e12, allow_inf_nan=False)
    distributions_ytd: float = Field(default=0, ge=0, le=1e12, allow_inf_nan=False)
    employer_match_ytd: float = Field(default=0, ge=0, le=1e12, allow_inf_nan=False)
    beneficiary: str = ""
    beneficiary_relationship: str = ""
    beneficiary_share: int = Field(default=100, ge=0, le=100)
    dividend_election: str = "Reinvest"
    investment_objective: str = ""
    risk_tolerance: str = "Moderate"
    employer: str = ""


class AccountUpdate(BaseModel):
    revision: int = Field(ge=1)
    account: AccountInput


@router.post("/portal/accounts")
def add_account(body: AccountUpdate, request: Request):
    return save_account(body, request, None)


@router.put("/portal/accounts/{account_id}")
def edit_account(account_id: str, body: AccountUpdate, request: Request):
    return save_account(body, request, account_id)


def save_account(body, request, account_id):
    p, cid = own(request)
    doc = p.get(cid)
    a = body.account
    if (
        a.account_type not in ACCOUNT_TYPES
        or a.cash_balance > a.balance
        or a.opened_date > a.balance_as_of
    ):
        raise ApiError(
            422, "INVALID_ACCOUNT", "Check the account type, dates, and cash balance."
        )
    old = next((x for x in doc["accounts"] if x["account_id"] == account_id), None)
    if account_id and not old:
        raise ApiError(404, "ACCOUNT_NOT_FOUND", "Account not found.")
    account_id = account_id or "ACCT-" + secrets.token_hex(6).upper()
    entry = {
        **(old or {}),
        **a.model_dump(mode="json"),
        "account_id": account_id,
        "client_id": cid,
        "masked_identifier": "****" + a.last4,
        "currency": "USD",
        "status": "open",
        "source": "Client-entered record",
        "source_kind": "self_reported",
        "source_id": "CLIENT-REPORTED-" + account_id,
        "holdings": [],
        "holdings_note": "Enter or verify holdings separately; this is a client-entered balance snapshot.",
    }
    entry.pop("last4", None)
    doc["accounts"] = (
        [entry if x["account_id"] == account_id else x for x in doc["accounts"]]
        if old
        else doc["accounts"] + [entry]
    )
    return p.save(doc, body.revision)


class ActivityInput(BaseModel):
    revision: int = Field(ge=1)
    account_id: str
    date: date
    type: Literal[
        "deposit",
        "withdrawal",
        "transfer",
        "purchase",
        "sale",
        "dividend",
        "interest",
        "fee",
        "contribution",
        "rollover",
        "distribution",
        "beneficiary_update",
    ]
    description: str = Field(min_length=3, max_length=500)
    amount: float = Field(ge=0, le=1e12, allow_inf_nan=False)
    related_account_id: str | None = None


@router.post("/portal/activity")
def activity(body: ActivityInput, request: Request):
    p, cid = own(request)
    doc = p.get(cid)
    ids = {a["account_id"] for a in doc["accounts"]}
    if body.account_id not in ids or (
        body.related_account_id and body.related_account_id not in ids
    ):
        raise ApiError(403, "ACCOUNT_NOT_OWNED", "Choose your own accounts.")
    if body.type == "transfer" and (
        not body.related_account_id or body.related_account_id == body.account_id
    ):
        raise ApiError(
            422,
            "TRANSFER_ACCOUNTS",
            "Choose two different accounts for the historical transfer.",
        )
    if body.date > date.today():
        raise ApiError(422, "FUTURE_ACTIVITY", "Use the date of a past activity.")
    ref = "CLIENT-REPORTED-" + secrets.token_hex(6).upper()
    event = {
        "event_id": ref,
        "source_id": ref,
        "account_id": body.account_id,
        "date": body.date.isoformat(),
        "settlement_date": None,
        "type": body.type,
        "description": body.description,
        "summary": body.description,
        "amount": body.amount,
        "currency": "USD",
        "status": "client_reported",
        "counterparty": body.related_account_id,
        "value_change": None,
        "balance_after": None,
    }
    doc["activity"].insert(0, event)
    if body.type == "transfer":
        doc["activity"].insert(
            0,
            {
                **event,
                "event_id": ref + "-PAIR",
                "account_id": body.related_account_id,
                "counterparty": body.account_id,
                "description": "Incoming side: " + body.description,
            },
        )
    # History entries are recollections, not transactions or automatic balance adjustments.
    return p.save(doc, body.revision)


class DocumentInput(BaseModel):
    words: str = Field(max_length=8000)
    summary: str = Field(max_length=8000)
    account_id: str | None = None
    amount: float | None = Field(default=None, gt=0, le=1e12, allow_inf_nan=False)


@router.post("/portal/document")
def document(body: DocumentInput, request: Request):
    p, cid = own(request)
    return p.document(cid, body.words, body.summary, body.account_id, body.amount)


@router.get("/portal/requests")
def requests(request: Request):
    p, cid = own(request)
    return {"requests": p.requests(cid)}


@router.post("/portal/requests/{case_id}/archive")
def archive(case_id: str, request: Request):
    p, cid = own(request)
    case = p.store.get_case(case_id)
    if not case or case["client_id"] != cid:
        raise ApiError(404, "CASE_NOT_FOUND", "Request not found.")
    return p.archive(cid, case)


class SpeechInput(BaseModel):
    text: str = Field(min_length=1, max_length=2500)


@router.post('/portal/speech')
def speech(body: SpeechInput, request: Request):
    from backend.portal.speech import speak
    _, cid = own(request)
    if not body.text.strip():
        raise ApiError(422, 'EMPTY_SPEECH', 'Choose some text to read aloud.')
    return Response(content=speak(cid, body.text), media_type='audio/mpeg', headers={'Cache-Control': 'no-store', 'X-Speech-Provider': 'Amazon Polly'})
