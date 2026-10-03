"""Request-local Bedrock events. Never exposes prompts or reasoning-content blocks."""

import contextvars
import json
import time
from contextlib import contextmanager

_current = contextvars.ContextVar("agent_trace", default=None)
_agent = contextvars.ContextVar("agent_name", default="Agent")


class CancelledRun(BaseException):
    pass


@contextmanager
def capture(sink):
    trace = {"sink": sink, "events": [], "started": time.monotonic()}
    token = _current.set(trace)
    try:
        yield trace
    finally:
        _current.reset(token)


@contextmanager
def agent(name):
    token = _agent.set(name)
    emit("stage", message=name + " is working")
    try:
        yield
    finally:
        _agent.reset(token)


def emit(kind, **data):
    trace = _current.get()
    if trace is None:
        return
    event = {"type": kind, "agent": _agent.get(), **data}
    if kind != "token":
        trace["events"].append(event)
    trace["sink"](event)


def active():
    return _current.get() is not None


def diagnostics(trace):
    events = trace["events"]
    return {
        "models": sorted({e["model"] for e in events if e["type"] == "model_start"}),
        "tools": sorted({e["tool"] for e in events if e["type"] == "tool"}),
        "facts_cited": sorted(
            {e["source_id"] for e in events if e["type"] == "source"}
        ),
        "elapsed_ms": round((time.monotonic() - trace["started"]) * 1000),
        "input_tokens": sum(
            e.get("inputTokens", 0) for e in events if e["type"] == "usage"
        ),
        "output_tokens": sum(
            e.get("outputTokens", 0) for e in events if e["type"] == "usage"
        ),
        "confidence": "Not numerically calibrated. Consult source checks and the audit verdict.",
    }


def converse_stream(client, **kwargs):
    emit("model_start", model=kwargs["modelId"])
    response = client.converse_stream(**kwargs)
    blocks = {}
    stop = None
    try:
        for event in response["stream"]:
            if any(k.endswith("Exception") for k in event):
                raise RuntimeError("Bedrock stream failed")
            if "contentBlockStart" in event:
                v = event["contentBlockStart"]
                start = v.get("start", {})
                if "toolUse" in start:
                    blocks[v["contentBlockIndex"]] = {
                        "toolUse": {**start["toolUse"], "input": ""}
                    }
                    emit("tool", tool=start["toolUse"]["name"])
            if "contentBlockDelta" in event:
                v = event["contentBlockDelta"]
                delta = v["delta"]
                i = v["contentBlockIndex"]
                if "text" in delta:
                    blocks.setdefault(i, {"text": ""})["text"] += delta["text"]
                    emit("token", text=delta["text"], provisional=True)
                elif "toolUse" in delta:
                    piece = delta["toolUse"].get("input", "")
                    blocks[i]["toolUse"]["input"] += piece
                    emit("token", text=piece, provisional=True)
                # reasoningContent and signature blocks are intentionally ignored.
            if "messageStop" in event:
                stop = event["messageStop"]["stopReason"]
            if "metadata" in event:
                emit("usage", **event["metadata"].get("usage", {}))
    finally:
        response["stream"].close()
    content = []
    for i in sorted(blocks):
        block = blocks[i]
        if "toolUse" in block:
            block["toolUse"]["input"] = json.loads(block["toolUse"]["input"])
        content.append(block)
    if stop not in ("tool_use", "end_turn", "stop_sequence", "guardrail_intervened"):
        raise RuntimeError("Incomplete model output")
    return {
        "stopReason": stop,
        "output": {"message": {"role": "assistant", "content": content}},
    }
