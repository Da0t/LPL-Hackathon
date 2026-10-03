"""Authenticated SSE transport for real Bedrock content deltas and tool events."""

import asyncio
import json
import queue
import threading
from typing import Literal
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from backend.errors import ApiError
from backend.services.auth import require_staff
from backend.aws.telemetry import capture, agent, diagnostics, CancelledRun

router = APIRouter()
_slots = threading.BoundedSemaphore(4)


class AgentInput(BaseModel):
    operation: Literal[
        "plan",
        "brief",
        "reply-draft",
        "compliance-review",
        "next-steps",
        "investigation",
    ]
    instruction: str | None = Field(default=None, max_length=2000)
    draft: str | None = Field(default=None, max_length=2000)
    refresh: bool = False


@router.post("/staff/cases/{case_id}/agents/stream")
def stream(
    case_id: str,
    body: AgentInput,
    request: Request,
    _role: str = Depends(require_staff),
):
    service = request.app.state.staff
    service._case(case_id)
    if not _slots.acquire(blocking=False):
        raise ApiError(429, "AGENTS_BUSY", "The team is busy. Try again in a moment.")
    mode = request.app.state.settings.ai_mode
    events = queue.Queue(maxsize=512)
    cancel = threading.Event()

    def send(event):
        if cancel.is_set():
            raise CancelledRun()
        try:
            events.put(event, timeout=2)
        except queue.Full:
            raise CancelledRun()

    names = {
        "plan": "Forge",
        "brief": "Briefing",
        "reply-draft": "Reply drafter",
        "compliance-review": "Sentinel",
        "next-steps": "Next steps",
        "investigation": "Investigator",
    }

    def work():
        try:
            with capture(send) as trace, agent(names[body.operation]):
                if body.operation == "plan":
                    result = service.plan(case_id, mode, refresh=body.refresh)
                elif body.operation == "reply-draft":
                    result = service.reply_draft(case_id, body.instruction, mode)
                elif body.operation == "compliance-review":
                    result = service.compliance_review(case_id, body.draft, mode)
                else:
                    result = getattr(service, body.operation.replace("-", "_"))(
                        case_id, mode, refresh=body.refresh
                    )
                result["diagnostics"] = diagnostics(trace)
                send({"type": "result", "result": result})
        except CancelledRun:
            pass
        except Exception as e:
            if not cancel.is_set():
                try:
                    send(
                        {
                            "type": "error",
                            "code": e.error_code
                            if isinstance(e, ApiError)
                            else "AGENT_FAILED",
                            "message": e.message
                            if isinstance(e, ApiError)
                            else "This agent could not complete. Try again.",
                        }
                    )
                except CancelledRun:
                    pass
        finally:
            _slots.release()
            if not cancel.is_set():
                try:
                    events.put({"type": "done"}, timeout=1)
                except queue.Full:
                    pass

    async def generate():
        threading.Thread(target=work, daemon=True).start()
        try:
            while not cancel.is_set():
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.to_thread(events.get, True, 1)
                except queue.Empty:
                    yield ": keep-alive\n\n"
                    continue
                yield (
                    "data: "
                    + json.dumps(event, ensure_ascii=False, default=str)
                    + "\n\n"
                )
                if event["type"] == "done":
                    break
        finally:
            cancel.set()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
