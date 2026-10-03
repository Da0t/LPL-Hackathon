"""HTTP routes for the SamePage version-one contract (Agent 2).

Frozen contract (contracts/API_V1.md):

    POST /intake/start
    POST /intake/{session_id}/turn
    POST /intake/{session_id}/confirm
    GET  /staff/cases
    GET  /staff/cases/{case_id}
    GET  /staff/cases/{case_id}/candidates
    POST /staff/cases/{case_id}/assign

Additive helper endpoints: GET /health, GET /demo/clients, POST /demo/reset.
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query, Request

from backend.errors import ApiError

from backend.schemas import (
    AssignRequest,
    AssignResponse,
    CandidatesResponse,
    CaseRecord,
    DemoClientsResponse,
    ErrorResponse,
    HealthResponse,
    IntakeConfirmRequest,
    IntakeConfirmResponse,
    IntakeStartRequest,
    IntakeStartResponse,
    IntakeTurnRequest,
    IntakeTurnResponse,
    ResetResponse,
    StaffCasesResponse,
)
from backend.services.auth import check_demo_client, demo_client_id, require_client, require_staff

router = APIRouter()

_ERRORS = {
    400: {"model": ErrorResponse, "description": "Bad request"},
    403: {"model": ErrorResponse, "description": "Demo role or demo client not permitted (simulated access control)"},
    404: {"model": ErrorResponse, "description": "Not found"},
    409: {"model": ErrorResponse, "description": "Conflict with current state"},
    422: {"model": ErrorResponse, "description": "Validation error"},
}


def _intake(request: Request):
    return request.app.state.intake


def _staff(request: Request):
    return request.app.state.staff


# ------------------------------------------------------------------ intake


@router.post("/intake/start", response_model=IntakeStartResponse, responses=_ERRORS, tags=["intake"])
def intake_start(body: IntakeStartRequest, request: Request, _role: str = Depends(require_client)):
    check_demo_client(request, body.client_id)
    session = _intake(request).start(body.client_id)
    return IntakeStartResponse(
        session_id=session["session_id"],
        client_display_name=session["client_display_name"],
        status=session["status"],
        client_id=session["client_id"],
        ai_mode=request.app.state.settings.ai_mode,
    )


@router.post("/intake/{session_id}/turn", response_model=IntakeTurnResponse, responses=_ERRORS, tags=["intake"])
def intake_turn(session_id: str, body: IntakeTurnRequest, request: Request, _role: str = Depends(require_client)):
    service = _intake(request)
    check_demo_client(request, service.get_session(session_id)["client_id"])
    return IntakeTurnResponse(**service.turn(session_id, body.text, body.input_mode, body.selected_option_id))


@router.post("/intake/{session_id}/confirm", response_model=IntakeConfirmResponse, responses=_ERRORS, tags=["intake"])
def intake_confirm(session_id: str, body: IntakeConfirmRequest, request: Request, _role: str = Depends(require_client)):
    service = _intake(request)
    check_demo_client(request, service.get_session(session_id)["client_id"])
    return IntakeConfirmResponse(**service.confirm(session_id, body.confirmed_plain_language_request, body.selected_account_id, body.amount_requested))


# ------------------------------------------------------------------- staff


@router.get("/staff/cases", response_model=StaffCasesResponse, responses=_ERRORS, tags=["staff"])
def staff_cases(
    request: Request,
    status: str | None = Query(default=None, description="Optional status filter"),
    category: str | None = Query(default=None, description="Optional category filter"),
    _role: str = Depends(require_staff),
):
    return StaffCasesResponse(cases=_staff(request).list_cases(status=status, category=category))


@router.get("/staff/cases/{case_id}", response_model=CaseRecord, responses=_ERRORS, tags=["staff"])
def staff_case(case_id: str, request: Request, _role: str = Depends(require_staff)):
    return _staff(request).get_case(case_id)


@router.get("/staff/cases/{case_id}/candidates", response_model=CandidatesResponse, responses=_ERRORS, tags=["staff"])
def staff_candidates(case_id: str, request: Request, _role: str = Depends(require_staff)):
    return CandidatesResponse(**_staff(request).candidates(case_id))


@router.post("/staff/cases/{case_id}/assign", response_model=AssignResponse, responses=_ERRORS, tags=["staff"])
def staff_assign(case_id: str, body: AssignRequest, request: Request, _role: str = Depends(require_staff)):
    return AssignResponse(**_staff(request).assign(case_id, body.advisor_id, body.staff_reason))


def _refresh(body: dict | None) -> bool:
    """Agent endpoints reuse their last answer for an unchanged case unless asked to regenerate."""
    return bool((body or {}).get("refresh"))


@router.post("/staff/cases/{case_id}/brief", responses=_ERRORS, tags=["staff"])
def staff_brief(case_id: str, request: Request, body: dict | None = Body(default=None), _role: str = Depends(require_staff)):
    """Read-only Bedrock-generated advisor prep brief for a case (additive, not in v1)."""
    return _staff(request).brief(case_id, request.app.state.settings.ai_mode, refresh=_refresh(body))


@router.post("/staff/cases/{case_id}/action", responses=_ERRORS, tags=["staff"])
def staff_action(case_id: str, body: dict, request: Request, _role: str = Depends(require_staff)):
    """Record an advisor workflow action (claim/note/clarify/schedule/resolve/approve/escalate) as a history event."""
    return _staff(request).action(case_id, body.get("action", ""), body.get("text"), body.get("compliance"),
                                  ai_mode=request.app.state.settings.ai_mode, acknowledged_flags=body.get("acknowledged_flags"))


@router.post("/staff/cases/{case_id}/plan", responses=_ERRORS, tags=["staff"])
def staff_plan(case_id: str, request: Request, _role: str = Depends(require_staff)):
    """Read-only Bedrock-prepared action packet (fields + compliance checks + drafts) for approval."""
    return _staff(request).plan(case_id, request.app.state.settings.ai_mode)


@router.post("/staff/cases/{case_id}/reply-draft", responses=_ERRORS, tags=["staff"])
def staff_reply_draft(case_id: str, request: Request, body: dict | None = Body(default=None), _role: str = Depends(require_staff)):
    """Drafter + compliance-reviewer loop for a client message (read-only, additive, not in v1)."""
    return _staff(request).reply_draft(case_id, (body or {}).get("instruction"), request.app.state.settings.ai_mode)


@router.get("/staff/cases/{case_id}/client", responses=_ERRORS, tags=["staff"])
def staff_client_snapshot(case_id: str, request: Request, _role: str = Depends(require_staff)):
    """The whole client behind a case: accounts, recent activity, other requests (read-only, additive)."""
    return _staff(request).client_snapshot(case_id)


@router.post("/staff/cases/{case_id}/next-steps", responses=_ERRORS, tags=["staff"])
def staff_next_steps(case_id: str, request: Request, body: dict | None = Body(default=None), _role: str = Depends(require_staff)):
    """Next-steps planner agent: ordered, owned steps for the request (read-only, additive)."""
    return _staff(request).next_steps(case_id, request.app.state.settings.ai_mode, refresh=_refresh(body))


@router.post("/staff/cases/{case_id}/investigation", responses=_ERRORS, tags=["staff"])
def staff_investigation(case_id: str, request: Request, body: dict | None = Body(default=None), _role: str = Depends(require_staff)):
    """Fraud investigator agent for security cases: record-built timeline plus an assessment (read-only, additive)."""
    return _staff(request).investigation(case_id, request.app.state.settings.ai_mode, refresh=_refresh(body))


@router.post("/staff/cases/{case_id}/compliance-review", responses=_ERRORS, tags=["staff"])
def staff_compliance_review(case_id: str, request: Request, body: dict | None = Body(default=None), _role: str = Depends(require_staff)):
    """Compliance reviewer on the case record and an optional draft (read-only, additive, not in v1)."""
    return _staff(request).compliance_review(case_id, (body or {}).get("draft"), request.app.state.settings.ai_mode)


# ------------------------------------------------- the client's own requests (additive)


def _signed_in_client(request: Request) -> str:
    client_id = demo_client_id(request)
    if not client_id:
        raise ApiError(400, "MISSING_DEMO_CLIENT", "Send X-Demo-Client-Id to see a client's own requests (simulated access control).")
    return client_id


@router.get("/my/requests", responses=_ERRORS, tags=["client"])
def my_requests(request: Request, _role: str = Depends(require_client)):
    """The signed-in client's requests and the messages exchanged on them. No staff-only fields."""
    return {"requests": request.app.state.client_requests.list(_signed_in_client(request))}


@router.post("/my/requests/{case_id}/reply", responses=_ERRORS, tags=["client"])
def my_request_reply(case_id: str, request: Request, body: dict | None = Body(default=None), _role: str = Depends(require_client)):
    """The client answers an advisor's question; the case goes back to the advisor."""
    return request.app.state.client_requests.reply(_signed_in_client(request), case_id, (body or {}).get("text"))


# --------------------------------------------------------- additive helpers


@router.get("/health", response_model=HealthResponse, tags=["demo"])
def health(request: Request):
    store = request.app.state.store
    adapter = request.app.state.adapter
    return HealthResponse(
        status="ok",
        ai_mode=request.app.state.settings.ai_mode,
        adapter=adapter.name,
        live_model=bool(adapter.live),
        data_source=store.data_source,
        counts=store.counts(),
        simulated_access_control=not bool(getattr(request.app.state, "portal", None)),
    )


@router.get("/demo/clients", response_model=DemoClientsResponse, tags=["demo"])
def demo_clients(request: Request):
    clients = request.app.state.store.list_clients()
    portal = getattr(request.app.state, "portal", None)
    if portal:
        actor = portal.actor(request)
        if actor["role"] == "client":
            clients = [c for c in clients if c["client_id"] == actor["client_id"]]
    return DemoClientsResponse(
        clients=[{"client_id": c["client_id"], "display_name": c["display_name"], "demo_scenario": c.get("demo_scenario")} for c in clients]
    )


@router.post("/demo/reset", response_model=ResetResponse, responses=_ERRORS, tags=["demo"])
def demo_reset(request: Request, _role: str = Depends(require_staff)):
    store = request.app.state.store
    store.reset_state()
    return ResetResponse(status="reset", data_source=store.data_source, counts=store.counts())
