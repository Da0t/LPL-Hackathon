"""A scripted fake bedrock-runtime client for testing the tool-use loop.

Lets us exercise the real ``_run_tool_loop`` orchestration (tool dispatch,
toolResult feedback, submit handling, guardrail stop) with no AWS credentials.
"""

from __future__ import annotations


def tool_use(tool_use_id: str, name: str, inp: dict) -> dict:
    """Build a Converse response whose assistant message calls one tool."""
    return {
        "stopReason": "tool_use",
        "output": {"message": {"role": "assistant", "content": [
            {"toolUse": {"toolUseId": tool_use_id, "name": name, "input": inp}}
        ]}},
    }


def guardrail_stop() -> dict:
    return {"stopReason": "guardrail_intervened",
            "output": {"message": {"role": "assistant", "content": [{"text": "blocked"}]}}}


class FakeBedrockClient:
    """Returns a pre-scripted sequence of converse() responses.

    ``script`` is a list of response dicts (use :func:`tool_use`). Each
    ``converse`` call returns the next one and records the kwargs it was given
    so tests can assert the loop fed tool results back to the model.
    """

    def __init__(self, script: list[dict]):
        self._script = list(script)
        self.calls: list[dict] = []

    def converse(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        if not self._script:
            raise AssertionError("FakeBedrockClient ran out of scripted responses")
        return self._script.pop(0)
