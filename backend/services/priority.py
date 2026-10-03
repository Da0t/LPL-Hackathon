"""Where a case is in the advisor workflow, and how soon it needs attention.

Pure functions over a case record, so the queue can explain every row in plain
words ("Waiting 2 days for an advisor") and survive a page reload.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

LEVELS = ("urgent", "high", "normal", "low", "done")
_HIGH_AFTER_HOURS = 24


def lifecycle_of(case: dict[str, Any]) -> str:
    events = {h.get("event") for h in case.get("history") or []}
    if "request_resolved" in events:
        return "resolved"
    if "meeting_scheduled" in events:
        return "scheduled"
    if case.get("status") == "needs_client_followup":
        return "awaiting_client"
    if case.get("status") == "assigned" or (case.get("routing") or {}).get("assigned_advisor_id"):
        return "assigned"
    if "escalated_to_security" in events:
        return "assigned"  # handed to the specialist team rather than to a named advisor
    return "new"


def _parse(stamp: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _hours_waiting(case: dict[str, Any], now: datetime) -> int:
    created = _parse(case.get("created_at"))
    return max(0, int((now - created).total_seconds() // 3600)) if created else 0


def intake_metrics(case: dict[str, Any]) -> dict[str, int] | None:
    """What the intake actually took: client turns, and seconds from the first
    message arriving to the client confirming. None for seeded cases, which had no intake."""
    turns = case.get("conversation") or []
    confirmed = _parse(case.get("client_confirmed_at"))
    started = _parse(turns[0].get("received_at") or turns[0].get("at")) if turns else None
    if not started or not confirmed:
        return None
    return {"turns": len(turns), "seconds_to_confirm": max(0, int((confirmed - started).total_seconds()))}


def _plural(n: int, unit: str) -> str:
    return f"{n} {unit}" + ("" if n == 1 else "s")


def priority_for(case: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    lifecycle = lifecycle_of(case)
    urgency = case.get("urgency") or {}
    history = case.get("history") or []
    if lifecycle == "resolved":
        level, reason = "done", "Resolved"
    elif "fraud_or_security" in (case.get("categories") or []):
        if any(h.get("event") == "escalated_to_security" for h in history):
            level, reason = "normal", "With the security specialist team"
        else:
            level, reason = "urgent", "Possible security issue, review first"
    elif urgency.get("level") in ("high", "urgent"):
        level, reason = "urgent", urgency.get("reason") or "Marked urgent"
    elif history and history[-1].get("event") == "client_replied":
        level, reason = "high", "The client replied"  # until the advisor acts on it
    elif lifecycle == "awaiting_client":
        level, reason = "low", "Waiting on the client's answer"
    elif lifecycle == "scheduled":
        level, reason = "low", "Meeting scheduled"
    elif lifecycle == "assigned":
        level, reason = "normal", "Assigned, not yet scheduled"
    else:
        hours = _hours_waiting(case, now)
        if hours >= _HIGH_AFTER_HOURS:
            level, reason = "high", f"Waiting {_plural(hours // 24, 'day')} for an advisor"
        elif hours < 1:
            level, reason = "normal", "New, just arrived"
        else:
            level, reason = "normal", f"New, waiting {_plural(hours, 'hour')} for an advisor"
    return {"level": level, "rank": LEVELS.index(level), "reason": reason}
