"""Drafter -> compliance reviewer -> (one revision) -> reviewer.

Pure orchestration: the two agents are passed in, nothing is saved, and the trace
records which agent did what so the dashboard can show the hand-offs.
"""

from __future__ import annotations

from typing import Any, Callable

MAX_REVISIONS = 1

DraftFn = Callable[..., dict[str, Any]]    # (case, instruction, findings=None, previous=None) -> {"message"}
ReviewFn = Callable[..., dict[str, Any]]   # (case, draft) -> {"verdict", "checks", "findings"}


def _review_summary(review: dict[str, Any]) -> str:
    findings = review.get("findings") or []
    if review.get("verdict") == "pass":
        return "Passed: no advice, promises, or unsupported facts in the draft."
    first = findings[0] if findings else {}
    detail = f' "{first["quote"]}": {first.get("issue", "")}' if first.get("quote") else ""
    return f"Flagged {len(findings)} issue(s).{detail}".strip()


def run_reply_workflow(case: dict[str, Any], instruction: str | None, draft_fn: DraftFn, review_fn: ReviewFn) -> dict[str, Any]:
    message = draft_fn(case, instruction)["message"]
    trace = [{"agent": "drafter", "step": "draft", "summary": "Wrote the first draft."}]
    review = review_fn(case, message)
    trace.append({"agent": "compliance", "step": "review", "summary": _review_summary(review)})

    revisions = 0
    while review["verdict"] != "pass" and revisions < MAX_REVISIONS:
        revisions += 1
        message = draft_fn(case, instruction, review["findings"], message)["message"]
        trace.append({"agent": "drafter", "step": "revise", "summary": "Revised the draft to resolve the reviewer's findings."})
        review = review_fn(case, message)
        trace.append({"agent": "compliance", "step": "review", "summary": _review_summary(review)})

    return {"draft": message, "review": review, "revised": revisions > 0, "trace": trace}
