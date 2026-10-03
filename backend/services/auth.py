"""Simulated access control for the hackathon demo (contracts/API_V1.md).

This is a **visible demo role switcher**, not production authentication.

* ``X-Demo-Role: client`` is required on ``/intake/*``; ``X-Demo-Role: staff`` on
  ``/staff/*`` and ``/demo/reset``. A ``demo_role`` query parameter is accepted for
  quick browser checks. When both are absent the configured default role applies
  (``client`` unless ``SAMEPAGE_DEFAULT_DEMO_ROLE`` says otherwise).
* Client calls also send ``X-Demo-Client-Id``. When present it must match the
  client the request is about (the body on ``/intake/start``, the session's client
  afterwards); a mismatch is refused. It may be omitted for curl-style checks.
"""

from __future__ import annotations

from fastapi import Depends, Request

from backend.errors import ApiError
from backend.settings import DEMO_ROLES

ROLE_HEADER = "X-Demo-Role"
CLIENT_HEADER = "X-Demo-Client-Id"
ROLE_QUERY = "demo_role"


def demo_role(request: Request) -> str:
    portal = getattr(request.app.state, "portal", None)
    if portal:
        return portal.actor(request)["role"]
    raw = request.headers.get(ROLE_HEADER) or request.query_params.get(ROLE_QUERY)
    if raw is None or not raw.strip():
        settings = getattr(request.app.state, "settings", None)
        raw = settings.default_demo_role if settings else "client"
    role = raw.strip().lower()
    if role not in DEMO_ROLES:
        raise ApiError(400, "INVALID_ROLE", f"Unknown demo role {raw!r}. Use X-Demo-Role: client or staff.")
    return role


def require_staff(role: str = Depends(demo_role)) -> str:
    if role != "staff":
        raise ApiError(
            403,
            "WRONG_DEMO_ROLE",
            "Use X-Demo-Role: staff for this endpoint (simulated access control for the hackathon demo).",
        )
    return role


def require_client(role: str = Depends(demo_role)) -> str:
    if role != "client":
        raise ApiError(
            403,
            "WRONG_DEMO_ROLE",
            "Use X-Demo-Role: client for intake endpoints (simulated access control for the hackathon demo).",
        )
    return role


def demo_client_id(request: Request) -> str | None:
    """The simulated signed-in client, if the page sent one."""
    portal = getattr(request.app.state, "portal", None)
    if portal:
        return portal.actor(request)["client_id"]
    raw = request.headers.get(CLIENT_HEADER)
    return raw.strip() if raw and raw.strip() else None


def check_demo_client(request: Request, expected_client_id: str) -> None:
    """Refuse a client call whose X-Demo-Client-Id names a different client."""
    sent = demo_client_id(request)
    if sent is not None and sent != expected_client_id:
        raise ApiError(
            403,
            "WRONG_DEMO_CLIENT",
            "X-Demo-Client-Id does not match the client this request belongs to "
            "(simulated access control: a client cannot act on another client's records).",
        )
