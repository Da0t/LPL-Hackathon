"""Advisor-workspace agents: a client-reply drafter and a compliance reviewer.

Both are single Bedrock tool-calls built on ``bedrock_agent._run_tool_loop`` (same
pacing, retries and Guardrail), and both have a deterministic offline fallback so
the dashboard works with no AWS credentials. Neither mutates a case; the loop that
makes them work together lives in ``backend.services.reply_workflow``.

    draft_reply(case, instruction, findings=None, previous=None) -> {"message": str}
    compliance_review(case, draft=None) -> {"verdict", "checks", "findings"}

``verdict`` is always computed here, never taken from the model: with a draft it is
``needs_changes`` iff the reviewer quoted a problem in the draft; without one it
reflects the case-record checks.
"""

from __future__ import annotations

import json
import re

from . import bedrock_agent as ba
from .config import AwsConfig, build_bedrock_client, load_config

CHECKS: list[tuple[str, str]] = [
    ("identity_confirmed", "Client identity confirmed"),
    ("no_advice", "No investment / tax advice given"),
    ("suitability", "Suitability considered"),
    ("account_confirmed", "Account confirmed with the client"),
]

_CASE_FACTS = (
    "client_display_name", "confirmed_plain_language_request", "original_words", "staff_summary",
    "categories", "amount_requested", "currency", "account_context", "unresolved_questions",
    "flags", "conflicts", "glossary", "client_meeting_preference",
)
_ADVISOR_EVENTS = ("advisor_note", "clarification_requested", "request_resolved")


def _facts(case: dict) -> str:
    return json.dumps({k: case.get(k) for k in _CASE_FACTS}, ensure_ascii=False, default=str)


def _advisor_texts(case: dict) -> list[str]:
    return [str(h["details"]["text"]) for h in case.get("history") or []
            if h.get("event") in _ADVISOR_EVENTS and (h.get("details") or {}).get("text")]


# --------------------------------------------------------------------------- #
# Reply drafter
# --------------------------------------------------------------------------- #
_DRAFT_SYSTEM = """You draft a short message from a wealth-management advisor to their client about a service request.

Hard rules:
- Plain, warm language a non-expert can follow. Explain any financial term in a few words, using the glossary text provided when there is one.
- Do NOT give investment, tax, or legal advice. Do NOT recommend, promise, or predict anything.
- Do NOT invent accounts, balances, amounts, dates, or history. Use only the facts provided.
- Ask only for what the advisor still needs from the client. Keep it under 120 words.
- If compliance findings are provided, rewrite the previous draft so that every finding is resolved.

Report the message by calling submit_draft exactly once."""

_DRAFT_TOOL = {
    "toolSpec": {
        "name": "submit_draft",
        "description": "Report the drafted client message. Call exactly once.",
        "inputSchema": {"json": {
            "type": "object",
            "properties": {"message": {"type": "string", "description": "The full message to the client, ready to send."}},
            "required": ["message"],
        }},
    }
}


def draft_reply(case: dict, instruction: str | None = None, findings: list[dict] | None = None,
                previous: str | None = None, *, cfg: AwsConfig | None = None, client=None) -> dict:
    """Draft (or, given ``findings`` and ``previous``, revise) a message to the client."""
    cfg = cfg or load_config()
    if not cfg.is_bedrock:
        return stub_draft_reply(case, instruction, findings, previous)
    if not cfg.model_id:
        raise ba.BedrockAdapterError("NO_MODEL_CONFIGURED", "BEDROCK_MODEL_ID is not set.")

    parts = ["Case facts:\n" + _facts(case)]
    if instruction:
        parts.append("What the advisor wants from this message:\n" + instruction)
    if previous:
        parts.append("Previous draft:\n" + previous)
    if findings:
        parts.append("Compliance findings to resolve:\n" + json.dumps(findings, ensure_ascii=False))
    client = client or build_bedrock_client(cfg)
    result = ba._run_tool_loop(client, cfg, ba._pacer_for(cfg), _DRAFT_SYSTEM, "\n\n".join(parts),
                               [_DRAFT_TOOL], "submit_draft", {})
    message = str(result.get("message") or "").strip()
    if not message:
        raise ba.BedrockAdapterError("EMPTY_DRAFT", "The model returned an empty draft.")
    return {"message": message}


_TELL_PREFIX = re.compile(
    r"^(?:please\s+)?(?:tell|let|ask|remind)\s+(?:her|him|them|the client)\s+(?:know\s+)?(?:that\s+)?", re.I)
_REVISION_SENTENCE = "Your advisor will go over the options with you when you speak."
_SIGN_OFF = "This note is about your request only and is not financial or tax advice."


def _to_client_voice(instruction: str) -> str:
    text = _TELL_PREFIX.sub("", instruction.strip())
    text = re.sub(r"\b(?:she|he|they)\b", "you", text, flags=re.I)
    text = re.sub(r"\b(?:her|his|their)\b", "your", text, flags=re.I)
    return text if text.endswith((".", "?", "!")) else text + "."


def stub_draft_reply(case: dict, instruction: str | None = None, findings: list[dict] | None = None,
                     previous: str | None = None) -> dict:
    """Deterministic drafter: a template built from the case's open questions."""
    if findings and previous:
        quotes = [str(f.get("quote") or "").lower() for f in findings if f.get("quote")]
        sentences = re.split(r"(?<=[.!?])\s+", previous.strip())
        kept = [s for s in sentences if not any(q in s.lower() for q in quotes)]
        if len(kept) < len(sentences) and _REVISION_SENTENCE not in kept:
            at = kept.index(_SIGN_OFF) if _SIGN_OFF in kept else len(kept)
            kept.insert(at, _REVISION_SENTENCE)
        return {"message": " ".join(kept)}

    first_name = (case.get("client_display_name") or "there").split()[0]
    sentences = [f"Hi {first_name}, thank you for your request."]
    questions = [q[0].lower() + q[1:] for q in case.get("unresolved_questions") or []
                 if q and "advisor review" not in q.lower()]
    if questions:
        sentences.append("Before we speak, it would help to know: " + "; ".join(questions) + ".")
    else:
        sentences.append("We have it, and an advisor will be in touch to go over it with you.")
    if instruction and instruction.strip():
        sentences.append("Your advisor also wanted to pass this along: " + _to_client_voice(instruction))
    sentences.append(_SIGN_OFF)
    return {"message": " ".join(sentences)}


# --------------------------------------------------------------------------- #
# Compliance reviewer
# --------------------------------------------------------------------------- #
_REVIEW_SYSTEM = """You are a compliance reviewer at a wealth-management firm. You review a service-request case and, when one is provided, a draft message to the client.

Assess each of these checks as "pass" or "attention", with one sentence of evidence taken from the facts provided:
- identity_confirmed: is there a record that the client's identity was confirmed?
- no_advice: do the advisor's notes and the draft avoid investment, tax, or legal advice, recommendations, promises, and predictions?
- suitability: are there open questions that must be answered before suitability can be judged?
- account_confirmed: does the record back the account the client means? A term-mismatch flag means it needs attention.

Hard rules:
- Use only the facts provided. If the record does not show something, the check is "attention"; never assume.
- For the draft, list a finding for every phrase that gives advice, recommends, promises, predicts, or states a fact the record does not support. Quote the exact words. No findings if the draft is clean or absent.

Report the review by calling submit_review exactly once."""

_REVIEW_TOOL = {
    "toolSpec": {
        "name": "submit_review",
        "description": "Report the compliance review. Call exactly once.",
        "inputSchema": {"json": {
            "type": "object",
            "properties": {
                "checks": {"type": "array", "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "enum": [c[0] for c in CHECKS]},
                        "status": {"type": "string", "enum": ["pass", "attention"]},
                        "evidence": {"type": "string"},
                    },
                    "required": ["id", "status", "evidence"],
                }},
                "findings": {"type": "array", "items": {
                    "type": "object",
                    "properties": {
                        "quote": {"type": "string", "description": "Exact words from the draft."},
                        "issue": {"type": "string"},
                        "suggestion": {"type": "string"},
                    },
                    "required": ["quote", "issue", "suggestion"],
                }},
            },
            "required": ["checks", "findings"],
        }},
    }
}


def compliance_review(case: dict, draft: str | None = None, *, cfg: AwsConfig | None = None, client=None) -> dict:
    """Review the case record and, if given, a draft client message."""
    cfg = cfg or load_config()
    if not cfg.is_bedrock:
        return stub_compliance_review(case, draft)
    if not cfg.model_id:
        raise ba.BedrockAdapterError("NO_MODEL_CONFIGURED", "BEDROCK_MODEL_ID is not set.")

    parts = ["Case facts:\n" + _facts(case),
             "Advisor notes and messages so far:\n" + json.dumps(_advisor_texts(case), ensure_ascii=False)]
    if draft:
        parts.append("Draft message to the client:\n" + draft)
    client = client or build_bedrock_client(cfg)
    result = ba._run_tool_loop(client, cfg, ba._pacer_for(cfg), _REVIEW_SYSTEM, "\n\n".join(parts),
                               [_REVIEW_TOOL], "submit_review", {})
    return _normalize_review(result, bool(draft))


def _verdict(checks: list[dict], findings: list[dict], has_draft: bool) -> str:
    if has_draft:
        return "needs_changes" if findings else "pass"
    return "pass" if all(c["status"] == "pass" for c in checks) else "needs_changes"


def _normalize_review(result: dict, has_draft: bool) -> dict:
    raw = result.get("checks")
    reported = {c.get("id"): c for c in raw if isinstance(c, dict)} if isinstance(raw, list) else {}
    checks = []
    for check_id, label in CHECKS:
        got = reported.get(check_id) or {}
        evidence = str(got.get("evidence") or "").strip()
        status = got.get("status") if got.get("status") in ("pass", "attention") and evidence else "attention"
        checks.append({"id": check_id, "label": label, "status": status,
                       "evidence": evidence or "Not assessed by the reviewer."})
    raw_findings = result.get("findings")
    findings = []
    for f in raw_findings if has_draft and isinstance(raw_findings, list) else []:
        if isinstance(f, dict) and (f.get("quote") or f.get("issue")):
            findings.append({k: str(f.get(k) or "").strip() for k in ("quote", "issue", "suggestion")})
    return {"verdict": _verdict(checks, findings, has_draft), "checks": checks, "findings": findings}


_RECOMMENDS = ("Reads as a recommendation to the client.", "Describe the options and leave the decision to the conversation.")
_PROMISES = ("Promises an outcome.", "Remove the promise; outcomes are not guaranteed.")
_TAX = ("States a tax outcome that has not been assessed.", "Say that tax effects will be reviewed, without stating them.")
_ADVICE_PATTERNS: list[tuple[re.Pattern[str], tuple[str, str]]] = [
    (re.compile(r"\b(?:you|she|he|they) should\b", re.I), _RECOMMENDS),
    (re.compile(r"\bI(?:'d| would)? (?:recommend|suggest|advise)\b", re.I), _RECOMMENDS),
    (re.compile(r"\bbest (?:option|choice)\b", re.I), _RECOMMENDS),
    (re.compile(r"\bguarantee[ds]?\b", re.I), _PROMISES),
    (re.compile(r"\btax[- ]free\b|\bwon'?t owe\b|\bno tax(?:es)?\b", re.I), _TAX),
]


def _advice_hits(text: str) -> list[dict]:
    hits = []
    for pattern, (issue, suggestion) in _ADVICE_PATTERNS:
        for match in pattern.finditer(text):
            hits.append({"quote": match.group(0), "issue": issue, "suggestion": suggestion})
    return hits


def stub_compliance_review(case: dict, draft: str | None = None) -> dict:
    """Deterministic reviewer: phrase rules for advice, record lookups for the rest."""
    flags = case.get("flags") or []
    notes = _advisor_texts(case)
    findings = _advice_hits(draft) if draft else []
    note_hits = [h for note in notes for h in _advice_hits(note)]

    if any(re.search(r"identity\s+(?:was\s+)?(?:confirmed|verified)|(?:confirmed|verified)\s+(?:the\s+client's\s+|their\s+)?identity", n, re.I) for n in notes):
        identity = ("pass", "An advisor note records that identity was confirmed.")
    else:
        extra = " Possible unauthorized access is flagged, so verify before discussing the account." if "possible_unauthorized_access" in flags else ""
        identity = ("attention", "No identity confirmation is recorded on this case yet." + extra)

    if note_hits or findings:
        where = "an advisor note" if note_hits else "the draft"
        advice = ("attention", f'Found "{(note_hits or findings)[0]["quote"]}" in {where}.')
    elif notes or draft:
        scope = " and ".join(([f"{len(notes)} advisor message(s)"] if notes else []) + (["the draft"] if draft else []))
        advice = ("pass", f"No recommendation or promise language found in {scope}.")
    else:
        advice = ("pass", "No advisor messages on this case yet, so nothing reads as advice.")

    unresolved = case.get("unresolved_questions") or []
    if unresolved:
        suitability = ("attention", "Open questions before suitability can be judged: " + "; ".join(unresolved) + ".")
    else:
        suitability = ("pass", "No open questions are recorded on the case.")

    ac = case.get("account_context") or {}
    if "client_term_did_not_match_account_type" in flags:
        account = ("attention", "The client's wording did not match the account type on record; confirm the account explicitly.")
    elif ac.get("masked_identifier"):
        kind = str(ac.get("account_label") or ac.get("account_type") or "account").replace("_", " ")
        account = ("pass", f"Client confirmed {kind} {ac['masked_identifier']} at intake (source {ac.get('account_source_id') or 'on record'}).")
    else:
        account = ("attention", "No account is linked to this case.")

    assessed = dict(zip((c[0] for c in CHECKS), (identity, advice, suitability, account)))
    checks = [{"id": cid, "label": label, "status": assessed[cid][0], "evidence": assessed[cid][1]} for cid, label in CHECKS]
    return {"verdict": _verdict(checks, findings, bool(draft)), "checks": checks, "findings": findings}


# --------------------------------------------------------------------------- #
# Next-steps planner
# --------------------------------------------------------------------------- #
OWNERS = ("advisor", "client", "operations")

_PLAN_SYSTEM = """You plan the work for a wealth-management advisor handling a client service request.

Produce the concrete steps to move the request forward, in the order they should happen. Each step has an owner:
"advisor" (the advisor does it), "client" (the client must answer or provide something), or "operations" (paperwork or processing).

Hard rules:
- Steps are process, not advice. Do NOT say what the client should decide, and do NOT state tax, eligibility, or suitability conclusions.
- Use only the facts provided. Do NOT invent accounts, balances, forms by number, or dates.
- If a flag says the client's wording did not match the account on record, confirming the account is the first step.
- 3 to 7 steps. Short titles (under 8 words); one sentence of detail each.

Report the plan by calling submit_plan exactly once."""

_PLAN_TOOL = {
    "toolSpec": {
        "name": "submit_plan",
        "description": "Report the next-steps plan. Call exactly once.",
        "inputSchema": {"json": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "One sentence: what has to happen for this request to move forward."},
                "steps": {"type": "array", "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "detail": {"type": "string"},
                        "owner": {"type": "string", "enum": list(OWNERS)},
                    },
                    "required": ["title", "detail", "owner"],
                }},
            },
            "required": ["summary", "steps"],
        }},
    }
}


def plan_next_steps(case: dict, *, cfg: AwsConfig | None = None, client=None) -> dict:
    """Turn a confirmed request into ordered, owned steps. Never mutates the case."""
    cfg = cfg or load_config()
    if not cfg.is_bedrock:
        return stub_plan_next_steps(case)
    if not cfg.model_id:
        raise ba.BedrockAdapterError("NO_MODEL_CONFIGURED", "BEDROCK_MODEL_ID is not set.")
    client = client or build_bedrock_client(cfg)
    result = ba._run_tool_loop(client, cfg, ba._pacer_for(cfg), _PLAN_SYSTEM, "Case facts:\n" + _facts(case),
                               [_PLAN_TOOL], "submit_plan", {})
    steps = []
    for s in result.get("steps") if isinstance(result.get("steps"), list) else []:
        if isinstance(s, dict) and str(s.get("title") or "").strip():
            steps.append({"title": str(s["title"]).strip(), "detail": str(s.get("detail") or "").strip(),
                          "owner": s.get("owner") if s.get("owner") in OWNERS else "advisor"})
    if not steps:
        raise ba.BedrockAdapterError("EMPTY_PLAN", "The model returned no steps.")
    return {"summary": str(result.get("summary") or "").strip(), "steps": steps[:8]}


def _step(title: str, detail: str, owner: str = "advisor") -> dict:
    return {"title": title, "detail": detail, "owner": owner}


def stub_plan_next_steps(case: dict) -> dict:
    """Deterministic planner: steps keyed off the case's flags, open questions and categories."""
    cats = case.get("categories") or []
    ac = case.get("account_context") or {}
    account = " ".join(str(x) for x in (ac.get("account_label") or str(ac.get("account_type") or "").replace("_", " "), ac.get("masked_identifier")) if x) or "the account"
    steps: list[dict] = []

    if "fraud_or_security" in cats:
        steps.append(_step("Verify the client's identity", "Use the specialist team's process and contact details already on file before discussing the account."))
        steps.append(_step("Review the activity with the client", "Go through what they did not recognize and when they noticed it."))
        steps.append(_step("Hold other requests until cleared", "Do not process other changes for this client until the specialist review is complete.", "operations"))
    if "client_term_did_not_match_account_type" in (case.get("flags") or []):
        said = f' They said: "{case["original_words"]}"' if case.get("original_words") else ""
        steps.append(_step("Confirm the account with the client", f"Their wording did not match the record, which shows {account}.{said}"))
    for q in case.get("unresolved_questions") or []:
        text = q[0].lower() + q[1:]
        if "advisor review" in text:
            steps.append(_step("Review: " + text.replace(" for advisor review", ""), "For the advisor to look into before the conversation. Nothing has been assessed yet."))
        else:
            steps.append(_step("Ask the client: " + text, "Needed before the request can move forward.", "client"))

    amount = case.get("amount_requested")
    if "withdrawal_or_distribution" in cats or "retirement_income" in cats:
        how_much = f" for ${amount:,.0f}" if isinstance(amount, (int, float)) else ""
        steps.append(_step("Prepare the distribution paperwork", f"Distribution request from {account}{how_much}. Do not submit until the client has spoken with the advisor.", "operations"))
    if "rollover_or_transfer" in cats:
        steps.append(_step("Identify both accounts in the transfer", "Confirm where the money is coming from and where it is going."))
        steps.append(_step("Prepare the transfer paperwork", "Transfer request for the accounts the client confirms.", "operations"))
    if "beneficiary_or_estate" in cats:
        steps.append(_step("Get the new beneficiary's details", "Full legal name and relationship to the client.", "client"))
        steps.append(_step("Send the beneficiary change form", f"For {account}. The change takes effect only once the signed form is processed.", "operations"))
    if "investment_planning" in cats:
        steps.append(_step("Check contribution eligibility and limits", "Look these up for the client's situation before the conversation; nothing has been assessed yet."))
    if not steps:
        steps.append(_step("Clarify what the client needs", "The request does not map to a standard process yet."))

    preference = case.get("client_meeting_preference")
    steps.append(_step("Schedule the conversation", f"The client prefers {preference} meetings." if preference else "Agree a time with the client."))
    waiting = sum(1 for s in steps if s["owner"] == "client")
    summary = f"{len(steps)} steps to move this request forward" + (f"; {waiting} need an answer from the client." if waiting else ".")
    return {"summary": summary, "steps": steps}


# --------------------------------------------------------------------------- #
# Fraud investigator (security cases). The timeline is always built from records
# by the caller; the agent only assesses it.
# --------------------------------------------------------------------------- #
RISK_LEVELS = ("low", "medium", "high")
_MONEY_EVENTS = ("transfer", "withdrawal", "distribution")

_INVESTIGATE_SYSTEM = """You support a security specialist at a wealth-management firm reviewing a client's report of possible unauthorized access.

Given the case facts and a timeline built from account records, assess:
- risk_level: "low", "medium", or "high".
- reasons: 2-4 short reasons, each citing the timeline entry's source id in parentheses when it relies on one.
- recommended_steps: 3-5 protective steps for the specialist to consider, in order.

Hard rules:
- Use only the facts and timeline provided. Do NOT invent events, devices, locations, or amounts.
- Do NOT state that fraud occurred; describe what the records show and what is unverified.
- Steps are suggestions for a human specialist. Nothing is frozen, reversed, or sent by you.

Report by calling submit_investigation exactly once."""

_INVESTIGATE_TOOL = {
    "toolSpec": {
        "name": "submit_investigation",
        "description": "Report the security assessment. Call exactly once.",
        "inputSchema": {"json": {
            "type": "object",
            "properties": {
                "risk_level": {"type": "string", "enum": list(RISK_LEVELS)},
                "reasons": {"type": "array", "items": {"type": "string"}},
                "recommended_steps": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["risk_level", "reasons", "recommended_steps"],
        }},
    }
}


def investigate_security(case: dict, timeline: list[dict], *, cfg: AwsConfig | None = None, client=None) -> dict:
    """Assess a security case against a record-built timeline. Never mutates the case."""
    cfg = cfg or load_config()
    if not cfg.is_bedrock:
        return stub_investigate_security(case, timeline)
    if not cfg.model_id:
        raise ba.BedrockAdapterError("NO_MODEL_CONFIGURED", "BEDROCK_MODEL_ID is not set.")
    client = client or build_bedrock_client(cfg)
    first_user = "Case facts:\n" + _facts(case) + "\n\nTimeline from account records:\n" + json.dumps(timeline, ensure_ascii=False, default=str)
    result = ba._run_tool_loop(client, cfg, ba._pacer_for(cfg), _INVESTIGATE_SYSTEM, first_user,
                               [_INVESTIGATE_TOOL], "submit_investigation", {})
    as_list = lambda v: [str(x).strip() for x in v if str(x).strip()] if isinstance(v, list) else []
    return {"risk_level": result.get("risk_level") if result.get("risk_level") in RISK_LEVELS else "medium",
            "reasons": as_list(result.get("reasons")), "recommended_steps": as_list(result.get("recommended_steps"))}


def stub_investigate_security(case: dict, timeline: list[dict]) -> dict:
    """Deterministic investigator: reads alerts and later money movement off the timeline."""
    alerts = [t for t in timeline if t.get("type") == "security_alert"]
    reasons = []
    if case.get("original_words"):
        reasons.append(f'The client reports: "{case["original_words"]}"')
    for alert in alerts:
        reasons.append(f"A security alert is on record for {alert.get('account') or 'an account'} on {alert['date']} ({alert['source_id']}).")
    if alerts:
        since = min(a["date"] for a in alerts)
        moved = [t for t in timeline if t.get("type") in _MONEY_EVENTS and t["date"] >= since]
        if moved:
            reasons.extend(f"A {t['type']} on {t['date']} followed the alert ({t['source_id']})." for t in moved)
        else:
            reasons.append("No transfers or withdrawals are on record since the alert.")
    else:
        reasons.append("No security alert is on record for this client's accounts, so the report cannot be matched to an event yet.")
    return {
        "risk_level": "high" if alerts else "medium",
        "reasons": reasons,
        "recommended_steps": [
            "Verify the client's identity using contact details already on file, not the ones in the alert.",
            "Go through recent sign-ins and devices with the client.",
            "Ask the specialist team whether to place a temporary hold on outgoing transfers.",
            "Have the client reset their password and sign-in verification.",
            "Hold other requests from this client until the review is complete.",
        ],
    }
