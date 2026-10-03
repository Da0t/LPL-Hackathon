"""Small shared helpers."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_session_id() -> str:
    return f"SESS-{secrets.token_hex(4)}"


MAX_MESSAGE_CHARS = 2000


def clean_text(value: object, what: str = "The text") -> str | None:
    """Free text from a request body: stripped, or None when absent or blank.
    Refuses anything that is not a string, and anything too long to be a message."""
    from backend.errors import ApiError  # local import: errors has no dependency on this module

    if value is None:
        return None
    if not isinstance(value, str):
        raise ApiError(400, "INVALID_TEXT", f"{what} must be plain text.")
    if len(value) > MAX_MESSAGE_CHARS:
        raise ApiError(400, "MESSAGE_TOO_LONG", f"{what} is too long. Keep it under {MAX_MESSAGE_CHARS:,} characters.")
    return value.strip() or None
