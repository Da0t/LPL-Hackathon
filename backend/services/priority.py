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
    return "new"


def _hours_waiting(case: dict[str, Any], now: datetime) -> int:
    try:
        created = datetime.fromisoformat(str(case.get("created_at")).replace("Z", "+00:00"))
    except ValueError:
        return 0
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return max(0, int((now - created).total_seconds() // 3600))


def _plural(n: int, unit: str) -> str:
    return f"{n} {unit}" + ("" if n == 1 else "s")


def priority_for(case: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    lifecycle = lifecycle_of(case)
    urgency = case.get("urgency") or {}
    if lifecycle == "resolved":
        level, reason = "done", "Resolved"
    elif "fraud_or_security" in (case.get("categories") or []):
        level, reason = "urgent", "Possible security issue, review first"
    elif urgency.get("level") in ("high", "urgent"):
        level, reason = "urgent", urgency.get("reason") or "Marked urgent"
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
