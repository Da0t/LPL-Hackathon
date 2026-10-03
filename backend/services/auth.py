"""Simulated access control for the hackathon demo.

This is a **visible demo role switcher**, not production authentication. The
role arrives in the ``X-Demo-Role`` header (``client`` or ``staff``); a
``demo_role`` query parameter is accepted for quick browser checks. When the
header is absent the configured default role applies (``client`` unless
``SAMEPAGE_DEFAULT_DEMO_ROLE`` says otherwise).
"""

from __future__ import annotations

from fastapi import Depends, Request

from backend.errors import ApiError
from backend.settings import DEMO_ROLES

ROLE_HEADER = "X-Demo-Role"
ROLE_QUERY = "demo_role"


def demo_role(request: Request) -> str:
    raw = request.headers.get(ROLE_HEADER) or request.query_params.get(ROLE_QUERY)
    if raw is None or not raw.strip():
        settings = getattr(request.app.state, "settings", None)
        raw = settings.default_demo_role if settings else "client"
    role = raw.strip().lower()
    if role not in DEMO_ROLES:
        raise ApiError(400, "invalid_role", f"Unknown demo role {raw!r}. Use one of {', '.join(DEMO_ROLES)}.")
    return role


def require_staff(role: str = Depends(demo_role)) -> str:
    if role != "staff":
        raise ApiError(
            403,
            "forbidden",
            "This endpoint requires the staff demo role. Send header 'X-Demo-Role: staff' "
            "(simulated access control for the hackathon demo).",
        )
    return role


def require_client(role: str = Depends(demo_role)) -> str:
    if role != "client":
        raise ApiError(
            403,
            "forbidden",
            "Intake endpoints require the client demo role. Send header 'X-Demo-Role: client' "
            "(simulated access control for the hackathon demo).",
        )
    return role
