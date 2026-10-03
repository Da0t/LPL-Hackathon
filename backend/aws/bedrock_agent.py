"""Amazon Bedrock intake and triage adapter for SamePage (Agent 1).

Exports the two functions frozen in ``contracts/API_V1.md``::

    intake_turn(client_id, transcript, selected_option_id, tools) -> dict
    triage_case(confirmed_request, tools) -> dict

Design choices (see AWS_SETUP.md for the "why"):

* **Native tool use via the Bedrock Converse API.** The model reads the
  client's real accounts and approved glossary through narrow, scoped tools,
  then emits its answer by calling a ``submit_*`` tool whose inputSchema *is*
  the result shape. Deterministic parsing, no JSON-scraping from prose, and it
  works uniformly across the allowlist (Claude, Nova, Llama).
* **Account/client scoping is enforced here, not trusted to the model.** The
  model-facing read tools take no identifiers; this adapter injects the
  authorized ``client_id`` / account id before calling the backend callbacks.
* **No invented facts.** The model may never assert an account, balance,
  history item, or amount. Missing data stays missing; uncertainty is surfaced.
* **Reliability.** Calls are paced (~1/sec) and retried with bounded backoff on
  throttling; a hard failure raises :class:`BedrockAdapterError` with a stable
  code/message so the backend can preserve the draft and offer typing or a
  person (per the contract's ``needs_clarification`` error behavior).

The ``tools`` object supplied by Agent 2 must provide these callbacks:

    get_relevant_accounts(client_id: str, phrase: str) -> list[dict]
        each: {account_id, account_type, familiar_label, masked_identifier?}
    get_approved_definition(term: str) -> dict | None   # {term, plain}
    get_relevant_account_history(account_id: str) -> list[dict]
        each: {type, date, source_id, summary?}
    search_advisor_directory(categories: list[str], preferences: dict) -> list[dict]
        each: {advisor_id, display_name, specialties, available}

Callbacks may be plain functions on the object (attribute access) or entries in
a mapping; both are supported.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Callable

from .config import AwsConfig, build_bedrock_client, load_config

logger = logging.getLogger("samepage.aws.bedrock")

# Category taxonomy frozen in SAMEPAGE_PRODUCT_SPEC.md / API_V1.md.
CATEGORIES = [
    "retirement_income",
    "withdrawal_or_distribution",
    "rollover_or_transfer",
    "beneficiary_or_estate",
    "investment_planning",
    "account_service",
    "fraud_or_security",
    "other_or_unclear",
]

# Error codes that are worth retrying with backoff.
_RETRYABLE_CODES = {
    "ThrottlingException",
    "ThrottledException",
    "TooManyRequestsException",
    "ModelTimeoutException",
    "ServiceUnavailableException",
    "InternalServerException",
    "ModelNotReadyException",
}

_MAX_TOOL_ITERATIONS = 6


class BedrockAdapterError(Exception):
    """Stable adapter failure the backend can map to a graceful response.

    The backend should catch this, keep the client's draft, set status
    ``needs_clarification``, show ``message``, and offer typing or a person.
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# --------------------------------------------------------------------------- #
# Pacing (shared across intake and triage so the whole app stays under ~1/sec)
# --------------------------------------------------------------------------- #
class _Pacer:
    def __init__(self, min_interval: float):
        self.min_interval = max(0.0, min_interval)
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self) -> None:
        if self.min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            delta = now - self._last
            if delta < self.min_interval:
                time.sleep(self.min_interval - delta)
            self._last = time.monotonic()


_PACER: _Pacer | None = None
_PACER_LOCK = threading.Lock()


def _pacer_for(cfg: AwsConfig) -> _Pacer:
    global _PACER
    with _PACER_LOCK:
        if _PACER is None or _PACER.min_interval != cfg.min_interval_seconds:
            _PACER = _Pacer(cfg.min_interval_seconds)
        return _PACER


# --------------------------------------------------------------------------- #
# Tool callback access (supports object-with-methods or a mapping)
# --------------------------------------------------------------------------- #
def _callback(tools: Any, name: str) -> Callable[..., Any]:
    fn = None
    if isinstance(tools, dict):
        fn = tools.get(name)
    else:
        fn = getattr(tools, name, None)
    if not callable(fn):
        raise BedrockAdapterError(
            "MISSING_TOOL_CALLBACK",
            f"The backend did not supply a '{name}' tool callback.",
        )
    return fn


# --------------------------------------------------------------------------- #
# Converse invocation with pacing + bounded retry
# --------------------------------------------------------------------------- #
def _invoke_converse(client, cfg: AwsConfig, pacer: _Pacer, **kwargs) -> dict:
    from botocore.exceptions import (
        ClientError,
        ConnectTimeoutError,
        EndpointConnectionError,
        ReadTimeoutError,
    )

    attempt = 0
    while True:
        pacer.wait()
        try:
            return client.converse(**kwargs)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "ClientError")
            request_id = exc.response.get("ResponseMetadata", {}).get("RequestId")
            if code in _RETRYABLE_CODES and attempt < cfg.max_retries:
                backoff = cfg.base_backoff_seconds * (2 ** attempt)
                logger.warning(
                    "bedrock retryable error code=%s request_id=%s attempt=%s backoff=%.2fs",
                    code, request_id, attempt, backoff,
                )
                time.sleep(backoff)
                attempt += 1
                continue
            logger.error("bedrock call failed code=%s request_id=%s", code, request_id)
            raise BedrockAdapterError(
                "BEDROCK_CALL_FAILED",
                "The assistant is temporarily unavailable. You can keep typing "
                "or ask to talk to a person.",
            ) from exc
        except (ReadTimeoutError, ConnectTimeoutError, EndpointConnectionError) as exc:
            if attempt < cfg.max_retries:
                backoff = cfg.base_backoff_seconds * (2 ** attempt)
                logger.warning("bedrock timeout attempt=%s backoff=%.2fs", attempt, backoff)
                time.sleep(backoff)
                attempt += 1
                continue
            logger.error("bedrock timeout exhausted retries")
            raise BedrockAdapterError(
                "BEDROCK_TIMEOUT",
                "The assistant took too long to respond. You can keep typing or "
                "ask to talk to a person.",
            ) from exc


# --------------------------------------------------------------------------- #
# Generic tool-use loop. Runs read tools until the model calls the submit tool.
# --------------------------------------------------------------------------- #
def _run_tool_loop(
    client,
    cfg: AwsConfig,
    pacer: _Pacer,
    system_prompt: str,
    first_user_text: str,
    tool_specs: list[dict],
    submit_tool_name: str,
    read_tool_dispatch: dict[str, Callable[[dict], Any]],
) -> dict:
    messages: list[dict] = [{"role": "user", "content": [{"text": first_user_text}]}]
    tool_config = {"tools": tool_specs, "toolChoice": {"auto": {}}}
    guardrail = cfg.guardrail_payload()

    for _ in range(_MAX_TOOL_ITERATIONS):
        kwargs: dict[str, Any] = {
            "modelId": cfg.model_id,
            "system": [{"text": system_prompt}],
            "messages": messages,
            "toolConfig": tool_config,
            "inferenceConfig": {
                "maxTokens": cfg.max_tokens,
                "temperature": cfg.temperature,
            },
        }
        if guardrail:
            kwargs["guardrailConfig"] = guardrail

        response = _invoke_converse(client, cfg, pacer, **kwargs)

        if response.get("stopReason") == "guardrail_intervened":
            raise BedrockAdapterError(
                "GUARDRAIL_BLOCKED",
                "That request can't be handled here. A person can help you with it.",
            )

        out_message = response.get("output", {}).get("message", {})
        content = out_message.get("content", []) or []
        messages.append({"role": "assistant", "content": content})

        tool_uses = [b["toolUse"] for b in content if "toolUse" in b]
        if not tool_uses:
            # Model answered in prose without calling submit_*. Nudge once.
            messages.append({
                "role": "user",
                "content": [{"text": f"Return your result by calling {submit_tool_name}."}],
            })
            continue

        submit_input: dict | None = None
        tool_results: list[dict] = []
        for use in tool_uses:
            name = use["name"]
            tool_use_id = use["toolUseId"]
            tool_input = use.get("input", {}) or {}
            if name == submit_tool_name:
                submit_input = tool_input
                tool_results.append({
                    "toolResult": {
                        "toolUseId": tool_use_id,
                        "content": [{"text": "recorded"}],
                    }
                })
                continue
            handler = read_tool_dispatch.get(name)
            if handler is None:
                tool_results.append({
                    "toolResult": {
                        "toolUseId": tool_use_id,
                        "content": [{"text": f"Unknown tool {name}."}],
                        "status": "error",
                    }
                })
                continue
            try:
                result = handler(tool_input)
                tool_results.append({
                    "toolResult": {
                        "toolUseId": tool_use_id,
                        "content": [{"json": {"result": result}}],
                    }
                })
            except BedrockAdapterError:
                raise
            except Exception as exc:  # a backend tool failed; tell the model, keep going
                logger.warning("tool '%s' raised: %s", name, exc)
                tool_results.append({
                    "toolResult": {
                        "toolUseId": tool_use_id,
                        "content": [{"text": "That lookup is unavailable right now."}],
                        "status": "error",
                    }
                })

        if submit_input is not None:
            return submit_input

        messages.append({"role": "user", "content": tool_results})

    raise BedrockAdapterError(
        "AGENT_NO_RESULT",
        "The assistant could not complete that step. You can keep typing or ask "
        "to talk to a person.",
    )


# --------------------------------------------------------------------------- #
# Intake
# --------------------------------------------------------------------------- #
_INTAKE_SYSTEM = """You are the SamePage intake assistant for a wealth-management firm.
You help a client describe, in plain language, which account and service they need, so a human advisor can help them.

Hard rules:
- You do NOT give investment, tax, or legal advice, and you do NOT recommend transactions.
- You NEVER invent an account, balance, transaction, or amount. Only reference accounts returned by list_my_accounts.
- If the client's words do not match any of their real accounts (for example they say "Roth" but no Roth account exists), do not claim that account exists. Set uncertainty explaining the mismatch and ask ONE gentle question proposing the closest real account.
- Offer at most THREE suggestions, each mapping to a real account id from list_my_accounts.
- Explain a financial term only by calling explain_term; never improvise a definition.
- When the client uses shorthand, an acronym, a spelled-out or phonetic fragment (for example "R O", "RMD", "my 401k"), or names a financial document loosely (for example "the tax form"), call suggest_financial_terms to get APPROVED candidate terms. Offer at most three of them and ask which the client means. Never assert a term the client has not confirmed, and never use a financial term that was not returned by suggest_financial_terms or explain_term.
- Ask at most ONE clarifying question per turn. Keep language simple and respectful; never assume the client's capacity.

Process:
1. Call list_my_accounts with the client's phrase to see their real accounts.
2. If the client uses shorthand, an acronym, or names a document, call suggest_financial_terms to map it to approved terms.
3. Call explain_term for any term you want to explain in plain words.
4. When ready, report your result by calling submit_intake exactly once."""

_INTAKE_TOOLS = [
    {
        "toolSpec": {
            "name": "list_my_accounts",
            "description": "List the authorized accounts for the current client that may relate to the phrase. Returns account_id, account_type, familiar_label, and masked_identifier.",
            "inputSchema": {"json": {
                "type": "object",
                "properties": {"phrase": {"type": "string", "description": "The client's current request wording."}},
                "required": ["phrase"],
            }},
        }
    },
    {
        "toolSpec": {
            "name": "explain_term",
            "description": "Return the approved plain-language definition of a financial term, or nothing if it is not in the approved glossary.",
            "inputSchema": {"json": {
                "type": "object",
                "properties": {"term": {"type": "string"}},
                "required": ["term"],
            }},
        }
    },
    {
        "toolSpec": {
            "name": "submit_intake",
            "description": "Report the intake interpretation. Call exactly once when ready.",
            "inputSchema": {"json": {
                "type": "object",
                "properties": {
                    "suggestions": {
                        "type": "array",
                        "maxItems": 3,
                        "items": {"type": "object", "properties": {
                            "id": {"type": "string"},
                            "label": {"type": "string"},
                            "account_id": {"type": "string"},
                        }, "required": ["id", "label"]},
                    },
                    "question": {"type": ["string", "null"], "description": "One clarifying question, or null."},
                    "definitions": {
                        "type": "array",
                        "items": {"type": "object", "properties": {
                            "term": {"type": "string"}, "plain": {"type": "string"},
                        }, "required": ["term", "plain"]},
                    },
                    "candidate_intent": {"type": ["string", "null"]},
                    "selected_account_id": {"type": ["string", "null"]},
                    "uncertainty": {"type": ["string", "null"]},
                },
                "required": ["suggestions", "question", "definitions", "candidate_intent", "selected_account_id", "uncertainty"],
            }},
        }
    },
]


_SUGGEST_TERMS_TOOL = {
    "toolSpec": {
        "name": "suggest_financial_terms",
        "description": "Map a client's shorthand, acronym, spelled-out/phonetic fragment, or loosely named document to approved glossary terms. Returns only approved candidates (term, plain). Use it, then confirm with the client; never invent a term.",
        "inputSchema": {"json": {
            "type": "object",
            "properties": {"fragment": {"type": "string", "description": "The client's wording to normalize, e.g. 'R O', 'RMD', 'the tax form'."}},
            "required": ["fragment"],
        }},
    }
}


def _get_optional_callback(tools: Any, name: str):
    fn = tools.get(name) if isinstance(tools, dict) else getattr(tools, name, None)
    return fn if callable(fn) else None


def intake_turn(
    client_id: str,
    transcript: str,
    selected_option_id: str | None,
    tools: Any,
    *,
    cfg: AwsConfig | None = None,
    client=None,
) -> dict:
    """Interpret one intake turn. Returns the AI portion of the /turn response.

    The backend adds ``session_id``, echoes ``transcript``, and sets ``status``.
    """
    cfg = cfg or load_config()
    if not cfg.is_bedrock:
        return _stub_intake(client_id, transcript, selected_option_id, tools)

    if not cfg.model_id:
        raise BedrockAdapterError(
            "NO_MODEL_CONFIGURED",
            "BEDROCK_MODEL_ID is not set. Configure a verified allowlisted model.",
        )

    pacer = _pacer_for(cfg)
    client = client or build_bedrock_client(cfg)

    get_accounts = _callback(tools, "get_relevant_accounts")
    get_definition = _callback(tools, "get_approved_definition")

    def _list_my_accounts(args: dict) -> list[dict]:
        # client_id is injected here, never taken from the model.
        rows = get_accounts(client_id=client_id, phrase=args.get("phrase", transcript)) or []
        safe = []
        for a in rows:
            safe.append({
                "account_id": a.get("account_id"),
                "account_type": a.get("account_type"),
                "familiar_label": a.get("familiar_label"),
                "masked_identifier": a.get("masked_identifier"),
            })
        return safe

    def _explain_term(args: dict) -> dict:
        return get_definition(term=args.get("term", "")) or {}

    dispatch = {"list_my_accounts": _list_my_accounts, "explain_term": _explain_term}

    # Term normalization is additive: offer the tool only if the backend supplies
    # a suggest_terms callback, so the frozen four-callback contract still works.
    tool_specs = _INTAKE_TOOLS
    suggest = _get_optional_callback(tools, "suggest_terms")
    if suggest is not None:
        def _suggest_financial_terms(args: dict) -> list[dict]:
            return suggest(args.get("fragment", "")) or []
        dispatch["suggest_financial_terms"] = _suggest_financial_terms
        tool_specs = _INTAKE_TOOLS[:-1] + [_SUGGEST_TERMS_TOOL, _INTAKE_TOOLS[-1]]

    hint = ""
    if selected_option_id:
        hint = f"\nThe client just selected suggestion id: {selected_option_id}."
    first_user = f"Client request: \"{transcript}\"{hint}"

    result = _run_tool_loop(
        client, cfg, pacer, _INTAKE_SYSTEM, first_user,
        tool_specs, "submit_intake", dispatch,
    )
    return _normalize_intake(result, tools, client_id)


def _normalize_intake(result: dict, tools: Any, client_id: str) -> dict:
    """Validate/shape the model's submit_intake payload; drop invented accounts."""
    get_accounts = _callback(tools, "get_relevant_accounts")
    valid_ids = {
        a.get("account_id") for a in (get_accounts(client_id=client_id, phrase="") or [])
    }

    suggestions = []
    for s in (result.get("suggestions") or [])[:3]:
        account_id = s.get("account_id") or s.get("id")
        # Only keep suggestions that map to a real account for this client.
        if account_id in valid_ids:
            suggestions.append({
                "id": account_id,
                "label": s.get("label") or "",
                "account_id": account_id,
            })

    selected = result.get("selected_account_id")
    if selected not in valid_ids:
        selected = None

    return {
        "suggestions": suggestions,
        "question": result.get("question"),
        "definitions": [
            {"term": d.get("term", ""), "plain": d.get("plain", "")}
            for d in (result.get("definitions") or [])
        ],
        "candidate_intent": result.get("candidate_intent"),
        "selected_account_id": selected,
        "uncertainty": result.get("uncertainty"),
    }


# --------------------------------------------------------------------------- #
# Triage
# --------------------------------------------------------------------------- #
_TRIAGE_SYSTEM = """You are the SamePage triage assistant for a wealth-management firm.
A client has already confirmed their request in their own words. You turn it into structured fields for human staff.

Hard rules:
- You do NOT give investment, tax, or legal advice and you do NOT decide routing; staff make the final decision.
- You NEVER invent accounts, balances, history, or amounts. If a fact is unknown, leave it out and add an unresolved question instead.
- Classify ONLY into these categories: {categories}. A case may have more than one.
- If the request involves unauthorized access, an unrecognized sign-in, fraud, or account takeover, include "fraud_or_security", add the flag "possible_unauthorized_access", and set routing_hint to "security_specialist_review". Never route such a case to a general advisor.
- You may call get_account_history and find_advisors to inform your summary, but the backend makes the final routing decision.

Write a warm plain-language client_summary and a precise staff_summary (describe the question, not advice). When ready, call submit_triage exactly once."""

_TRIAGE_TOOLS = [
    {
        "toolSpec": {
            "name": "get_account_history",
            "description": "Return relevant prior events for the confirmed account (type, date, source_id).",
            "inputSchema": {"json": {"type": "object", "properties": {}}},
        }
    },
    {
        "toolSpec": {
            "name": "find_advisors",
            "description": "Search the fictional advisor directory for candidates matching categories and preferences.",
            "inputSchema": {"json": {
                "type": "object",
                "properties": {
                    "categories": {"type": "array", "items": {"type": "string"}},
                    "preferences": {"type": "object"},
                },
                "required": ["categories"],
            }},
        }
    },
    {
        "toolSpec": {
            "name": "submit_triage",
            "description": "Report the structured triage result. Call exactly once when ready.",
            "inputSchema": {"json": {
                "type": "object",
                "properties": {
                    "client_summary": {"type": "string"},
                    "staff_summary": {"type": "string"},
                    "intent": {"type": "string"},
                    "categories": {"type": "array", "items": {"type": "string", "enum": CATEGORIES}, "minItems": 1},
                    "unresolved_questions": {"type": "array", "items": {"type": "string"}},
                    "flags": {"type": "array", "items": {"type": "string"}},
                    "recommended_advisor_ids": {"type": "array", "items": {"type": "string"}},
                    "routing_hint": {"type": ["string", "null"]},
                },
                "required": ["client_summary", "staff_summary", "intent", "categories", "unresolved_questions", "flags"],
            }},
        }
    },
]


def triage_case(
    confirmed_request: dict,
    tools: Any,
    *,
    cfg: AwsConfig | None = None,
    client=None,
) -> dict:
    """Classify a client-confirmed request into structured fields.

    ``confirmed_request`` should include at least
    ``confirmed_plain_language_request``; optional helpful keys are
    ``original_words``, ``selected_account_id``, ``amount_requested``,
    ``candidate_intent``. The backend attaches verified account facts and the
    final routing decision.
    """
    cfg = cfg or load_config()
    if not cfg.is_bedrock:
        return _stub_triage(confirmed_request, tools)

    if not cfg.model_id:
        raise BedrockAdapterError(
            "NO_MODEL_CONFIGURED",
            "BEDROCK_MODEL_ID is not set. Configure a verified allowlisted model.",
        )

    pacer = _pacer_for(cfg)
    client = client or build_bedrock_client(cfg)

    account_id = confirmed_request.get("selected_account_id")
    get_history = _callback(tools, "get_relevant_account_history")
    search_advisors = _callback(tools, "search_advisor_directory")

    def _get_account_history(_args: dict) -> list[dict]:
        if not account_id:
            return []
        return get_history(account_id=account_id) or []

    def _find_advisors(args: dict) -> list[dict]:
        return search_advisors(
            categories=args.get("categories", []),
            preferences=args.get("preferences", {}),
        ) or []

    dispatch = {"get_account_history": _get_account_history, "find_advisors": _find_advisors}

    system = _TRIAGE_SYSTEM.format(categories=", ".join(CATEGORIES))
    first_user = "Confirmed request:\n" + json.dumps({
        "confirmed_plain_language_request": confirmed_request.get("confirmed_plain_language_request"),
        "original_words": confirmed_request.get("original_words"),
        "candidate_intent": confirmed_request.get("candidate_intent"),
        "selected_account_id": account_id,
        "amount_requested": confirmed_request.get("amount_requested"),
    }, ensure_ascii=False)

    result = _run_tool_loop(
        client, cfg, pacer, system, first_user,
        _TRIAGE_TOOLS, "submit_triage", dispatch,
    )
    return _normalize_triage(result)


def _normalize_triage(result: dict) -> dict:
    categories = [c for c in (result.get("categories") or []) if c in CATEGORIES]
    if not categories:
        categories = ["other_or_unclear"]

    flags = list(result.get("flags") or [])
    routing_hint = result.get("routing_hint")
    # Safety net: a fraud/security case must never recommend a general advisor.
    if "fraud_or_security" in categories:
        if "possible_unauthorized_access" not in flags:
            flags.append("possible_unauthorized_access")
        routing_hint = "security_specialist_review"
        recommended = []
    else:
        recommended = list(result.get("recommended_advisor_ids") or [])

    return {
        "client_summary": result.get("client_summary", ""),
        "staff_summary": result.get("staff_summary", ""),
        "intent": result.get("intent", ""),
        "categories": categories,
        "unresolved_questions": list(result.get("unresolved_questions") or []),
        "flags": flags,
        "recommended_advisor_ids": recommended,
        "routing_hint": routing_hint,
    }


# --------------------------------------------------------------------------- #
# Advisor prep brief (read-only) , Bedrock-generated talking points for staff.
# --------------------------------------------------------------------------- #
_BRIEF_SYSTEM = """You prepare a financial advisor for a client conversation at a wealth-management firm.
Given a client-confirmed service request and record-backed facts, produce a concise, practical prep brief.

Hard rules:
- Do NOT give investment, tax, or legal advice and do NOT tell the advisor what the client should do.
- Do NOT invent accounts, balances, amounts, or history. Use only the facts provided.
- Frame talking points as things to discuss or clarify, not recommendations.
- Always include at least one compliance caution (e.g., confirm identity, no advice given, note suitability, tax not assessed).

Report the brief by calling submit_brief exactly once."""

_BRIEF_TOOL = {
    "toolSpec": {
        "name": "submit_brief",
        "description": "Report the advisor prep brief. Call exactly once.",
        "inputSchema": {"json": {
            "type": "object",
            "properties": {
                "headline": {"type": "string", "description": "One sentence: what this client is really asking for, in advisor terms."},
                "talking_points": {"type": "array", "items": {"type": "string"}, "description": "2-4 things to discuss, framed as questions/topics, not advice."},
                "confirm": {"type": "array", "items": {"type": "string"}, "description": "Facts or intentions to confirm with the client."},
                "cautions": {"type": "array", "items": {"type": "string"}, "description": "Compliance/risk cautions for the advisor."},
            },
            "required": ["headline", "talking_points", "confirm", "cautions"],
        }},
    }
}


def advisor_brief(case: dict, tools=None, *, cfg: AwsConfig | None = None, client=None) -> dict:
    """Generate a read-only advisor prep brief from a case's confirmed facts.

    ``case`` should carry confirmed_plain_language_request, staff_summary,
    categories, amount_requested, account_context, unresolved_questions, flags,
    conflicts, original_words. Never mutates the case. ``tools`` is unused today
    (facts are passed in the prompt) but accepted for signature symmetry.
    """
    cfg = cfg or load_config()
    if not cfg.is_bedrock:
        return _stub_brief(case)
    if not cfg.model_id:
        raise BedrockAdapterError("NO_MODEL_CONFIGURED", "BEDROCK_MODEL_ID is not set.")

    pacer = _pacer_for(cfg)
    client = client or build_bedrock_client(cfg)
    facts = {k: case.get(k) for k in (
        "confirmed_plain_language_request", "staff_summary", "categories", "intent",
        "amount_requested", "currency", "account_context", "unresolved_questions",
        "flags", "conflicts", "original_words",
    )}
    first_user = "Case facts:\n" + json.dumps(facts, ensure_ascii=False, default=str)
    result = _run_tool_loop(client, cfg, pacer, _BRIEF_SYSTEM, first_user, [_BRIEF_TOOL], "submit_brief", {})
    return _normalize_brief(result)


def _normalize_brief(result: dict) -> dict:
    as_list = lambda v: [str(x) for x in v] if isinstance(v, list) else ([str(v)] if v else [])
    cautions = as_list(result.get("cautions"))
    if not cautions:
        cautions = ["Confirm the client's identity. This is a service request, not advice; no transaction is authorized."]
    return {
        "headline": str(result.get("headline") or "").strip(),
        "talking_points": as_list(result.get("talking_points")),
        "confirm": as_list(result.get("confirm")),
        "cautions": cautions,
    }


def _stub_brief(case: dict) -> dict:
    cats = case.get("categories") or []
    points = []
    if "withdrawal_or_distribution" in cats or "retirement_income" in cats:
        points.append("Discuss the purpose and timing of the requested distribution.")
    if "rollover_or_transfer" in cats:
        points.append("Clarify which accounts are involved in the transfer.")
    if "beneficiary_or_estate" in cats:
        points.append("Review the current beneficiary designation and the requested change.")
    if "fraud_or_security" in cats:
        points.append("Verify identity and review the unrecognized activity before anything else.")
    if not points:
        points.append("Clarify what outcome the client is hoping for.")
    confirm = list(case.get("unresolved_questions") or []) or ["The account and intent the client confirmed."]
    cautions = ["This is a service request, not advice; no transaction is authorized.",
                "Confirm the client's identity before discussing account details."]
    if "client_term_did_not_match_account_type" in (case.get("flags") or []):
        cautions.append("Client used a term that did not match their records , confirm the account explicitly.")
    return {
        "headline": case.get("staff_summary") or case.get("confirmed_plain_language_request") or "Client service request.",
        "talking_points": points, "confirm": confirm, "cautions": cautions,
    }


# --------------------------------------------------------------------------- #
# Offline stub mode (SAMEPAGE_AI_MODE=stub) - dev only, never the judged path.
# --------------------------------------------------------------------------- #
def _stub_intake(client_id: str, transcript: str, selected_option_id, tools) -> dict:
    get_accounts = _callback(tools, "get_relevant_accounts")
    accounts = get_accounts(client_id=client_id, phrase=transcript) or []
    valid_ids = {a.get("account_id") for a in accounts}

    if selected_option_id in valid_ids:
        return {
            "suggestions": [],
            "question": None,
            "definitions": [],
            "candidate_intent": "account_service",
            "selected_account_id": selected_option_id,
            "uncertainty": None,
        }

    phrase = transcript.lower()
    said_roth = "roth" in phrase
    has_roth = any(a.get("account_type") == "roth_ira" for a in accounts)
    mismatch = said_roth and not has_roth

    suggestions = [
        {"id": a["account_id"], "label": a.get("familiar_label", ""), "account_id": a["account_id"]}
        for a in accounts[:3]
    ]
    definitions = []
    if mismatch:
        get_definition = _callback(tools, "get_approved_definition")
        d = get_definition(term="rollover IRA")
        if d:
            definitions = [{"term": d["term"], "plain": d["plain"]}]

    return {
        "suggestions": suggestions,
        "question": (
            "I don't see a Roth IRA here. Could you mean your rollover IRA from your former employer?"
            if mismatch else "Which of these accounts would you like to discuss?"
        ),
        "definitions": definitions,
        "candidate_intent": "discuss_possible_withdrawal" if mismatch else "account_service",
        "selected_account_id": None,
        "uncertainty": (
            "Client said Roth IRA; the authorized account list shows a rollover IRA instead."
            if mismatch else "The account has not been confirmed."
        ),
    }


def _stub_triage(confirmed_request: dict, tools) -> dict:
    text = " ".join(str(confirmed_request.get(k, "")) for k in
                     ("confirmed_plain_language_request", "original_words")).lower()
    security = any(w in text for w in ("sign-in", "sign in", "unauthorized", "fraud", "recognize", "takeover"))
    if security:
        return _normalize_triage({
            "client_summary": "We'll have someone review the sign-in you don't recognize.",
            "staff_summary": "Client reports a possible unauthorized sign-in and requests account-access review.",
            "intent": "review_account_access",
            "categories": ["fraud_or_security", "account_service"],
            "unresolved_questions": ["Time and device of the alert"],
            "flags": ["possible_unauthorized_access"],
            "routing_hint": "security_specialist_review",
        })
    return _normalize_triage({
        "client_summary": confirmed_request.get("confirmed_plain_language_request", ""),
        "staff_summary": "Client requests discussion of a possible distribution from a retirement account.",
        "intent": confirmed_request.get("candidate_intent") or "discuss_possible_withdrawal",
        "categories": ["withdrawal_or_distribution", "retirement_income"],
        "unresolved_questions": ["Desired timing", "Potential tax implications for advisor review"],
        "flags": ["client_term_did_not_match_account_type"],
        "recommended_advisor_ids": [],
        "routing_hint": "retirement_advisor_review",
    })
