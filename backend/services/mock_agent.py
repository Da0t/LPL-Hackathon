"""Deterministic mock of Agent 1's Bedrock adapter (Agent 2).

Same signatures as ``backend/aws/bedrock_agent.py``::

    intake_turn(client_id, transcript, selected_option_id, tools) -> dict
    triage_case(confirmed_request, tools) -> dict

It exists so the client and staff pages can be developed offline and so the
backend tests run without AWS. It is grounded in the same authorized tool
callbacks the real adapter receives and never invents account facts. The
judged demo path must use ``SAMEPAGE_AGENT_MODE=bedrock``.
"""

from __future__ import annotations

import re
from typing import Any

from backend.schemas import OPTION_NONE_OF_THESE, OPTION_TALK_TO_PERSON
from backend.services.text_rules import ACCOUNT_TYPE_LABELS, detect_security_concern, extract_amounts

ADAPTER_NAME = "mock"

INTENT_PATTERNS: tuple[tuple[str, str], ...] = (
    ("update_beneficiary", r"\bbeneficiar\w*\b|\bwho gets\b|\bwhen i (?:die|pass)\b|\bpass(?:es)? away\b|\binherit\w*\b"),
    ("discuss_required_minimum_distribution", r"\brmds?\b|\brequired minimum\b|\bminimum distribution\b"),
    ("discuss_rollover_or_transfer", r"\broll(?:ing)? (?:it |that |the money |my \w+ )?over\b|\btransfer\w*\b|\bmove (?:my |the |it\b|money\b|some money\b)|\bconsolidat\w*\b"),
    ("contribution_question", r"\bcontribut\w*\b|\bput (?:money )?in(?:to)?\b|\badd money\b"),
    ("discuss_possible_withdrawal", r"\bneed\b.*\b(?:\$|dollars|thousand|hundred|money)|\btake (?:some |the )?(?:money )?out\b|\bwithdraw\w*\b|\bcash out\b|\bpull (?:money )?out\b|\bget (?:some |the )?money\b|\buse (?:some |the )?money\b|\bmoney for\b|\bdistribution\b"),
    ("investment_planning_question", r"\binvest\w*\b|\bportfolio\b|\bmarket\b|\bstocks?\b|\ballocation\b|\brisk\b"),
    ("understand_options", r"\boptions?\b|\bwhat can i do\b|\bshould i\b|\bwhat happens if\b"),
)

INTENT_CATEGORIES: dict[str, list[str]] = {
    "discuss_possible_withdrawal": ["withdrawal_or_distribution", "retirement_income"],
    "understand_options": ["retirement_income"],
    "update_beneficiary": ["beneficiary_or_estate", "account_service"],
    "report_security_concern": ["fraud_or_security", "account_service"],
    "discuss_rollover_or_transfer": ["rollover_or_transfer"],
    "discuss_required_minimum_distribution": ["withdrawal_or_distribution", "retirement_income"],
    "contribution_question": ["account_service", "retirement_income"],
    "investment_planning_question": ["investment_planning"],
    "general_question": ["other_or_unclear"],
}

RETIREMENT_TYPES = {"rollover_ira", "roth_ira", "traditional_ira", "sep_ira", "simple_ira", "401k"}


def detect_intent(text: str) -> str:
    lowered = (text or "").lower()
    if detect_security_concern(lowered):
        return "report_security_concern"
    for intent, pattern in INTENT_PATTERNS:
        if re.search(pattern, lowered):
            return intent
    return "general_question"


def _type_label(account_type: str | None) -> str:
    if not account_type:
        return "account"
    return ACCOUNT_TYPE_LABELS.get(account_type, account_type.replace("_", " "))


def _friendly(account: dict[str, Any]) -> str:
    base = account.get("familiar_label") or account.get("label") or _type_label(account.get("account_type"))
    return f"{base} ({account.get('masked_identifier')})"


def _short(account: dict[str, Any]) -> str:
    return f"{account.get('label') or _type_label(account.get('account_type'))} ({account.get('masked_identifier')})"


def _mine(account: dict[str, Any]) -> str:
    """First-person phrasing: 'Rollover IRA from my former employer (****4821)'."""
    label = account.get("label") or _type_label(account.get("account_type"))
    if account.get("account_type") == "rollover_ira" and account.get("former_employer"):
        label = f"{label} from my former employer"
    return f"{label} ({account.get('masked_identifier')})"


def _interpretation(intent: str, account: dict[str, Any]) -> str:
    acct = _mine(account)
    return {
        "discuss_possible_withdrawal": f"Taking money out of my {acct}",
        "understand_options": f"Understanding my options for my {acct}",
        "update_beneficiary": f"Changing the beneficiary on my {acct}",
        "report_security_concern": f"Reporting activity I did not authorize on my {acct}",
        "discuss_rollover_or_transfer": f"Moving money involving my {acct}",
        "discuss_required_minimum_distribution": f"Required minimum distributions from my {acct}",
        "contribution_question": f"Contributing to my {acct}",
        "investment_planning_question": f"How my {acct} is invested",
    }.get(intent, f"A question about my {acct}")


def _third_person(purpose: str) -> str:
    return re.sub(r"\bmy\b", "the client's", re.sub(r"\bour\b", "the client's", purpose))


def _purpose(text: str) -> str:
    match = re.search(r"\bfor (my|our|the|a|an) ([^.,;!?]{3,60})", text or "", re.I)
    if not match:
        return ""
    purpose = match.group(2).strip()
    purpose = re.sub(r"\s+(it's|its|it is|that's|which|and)\b.*$", "", purpose, flags=re.I).strip()
    return f" for {match.group(1).lower()} {purpose}" if purpose else ""


def _amount_phrase(text: str) -> str:
    amounts = extract_amounts(text or "")
    if not amounts:
        return ""
    value = amounts[0]
    formatted = f"${value:,.0f}" if float(value).is_integer() else f"${value:,.2f}"
    return f"{formatted} "


def _definitions(tools: Any, terms: list[str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for term in terms:
        entry = tools["get_approved_definition"](term)
        if entry and all(d["term"] != entry["term"] for d in out):
            out.append({"term": entry["term"], "plain": entry["plain"]})
        if len(out) >= 3:
            break
    return out


def _proposed_request(intent: str, account: dict[str, Any] | None, transcript: str) -> str:
    where = f" from my {_mine(account)}" if account else " from my retirement account"
    about = f" my {_mine(account)}" if account else " my account"
    if intent == "discuss_possible_withdrawal":
        return f"I want to speak with an advisor about using {_amount_phrase(transcript)}{where.strip()}{_purpose(transcript)}.".replace("  ", " ")
    if intent == "understand_options":
        return f"I want to understand my options for{about} before deciding anything."
    if intent == "update_beneficiary":
        return f"I want to update who is named as beneficiary on{about}."
    if intent == "report_security_concern":
        return f"I am reporting activity on{about} that I did not authorize, and I want it reviewed right away."
    if intent == "discuss_rollover_or_transfer":
        return f"I want to talk with an advisor about moving money involving{about}."
    if intent == "discuss_required_minimum_distribution":
        return f"I have a question about required minimum distributions from{about}."
    if intent == "contribution_question":
        return f"I have a question about contributing to{about}."
    if intent == "investment_planning_question":
        return f"I have a question about how{about} is invested."
    return f"I would like to talk with someone about{about}."


def _intent_terms(intent: str) -> list[str]:
    return {
        "discuss_possible_withdrawal": ["withdrawal"],
        "update_beneficiary": ["beneficiary"],
        "discuss_rollover_or_transfer": ["transfer"],
        "discuss_required_minimum_distribution": ["required minimum distribution"],
        "report_security_concern": ["trusted contact"],
    }.get(intent, [])


def intake_turn(client_id: str, transcript: str, selected_option_id: str | None, tools: Any) -> dict[str, Any]:
    context = tools["get_session_context"]() if "get_session_context" in tools else {}
    lookup = tools["get_relevant_accounts"](client_id, transcript)
    accounts: list[dict[str, Any]] = lookup.get("accounts", [])
    by_id = {a["account_id"]: a for a in accounts}
    missing_types: list[str] = lookup.get("missing_account_types", [])
    former_employer = bool(lookup.get("former_employer_mentioned"))
    offered: set[str] = set(context.get("offered_account_ids") or [])
    last_selected = context.get("last_selected_option") or {}

    intent = context.get("candidate_intent") if last_selected.get("id") in {"opt-withdraw", "opt-options"} else None
    if last_selected.get("id") == "opt-options" and selected_option_id == "opt-options":
        intent = "understand_options"
    elif last_selected.get("id") == "opt-withdraw" and selected_option_id == "opt-withdraw":
        intent = "discuss_possible_withdrawal"
    if selected_option_id == "opt-options":
        intent = "understand_options"
    elif selected_option_id == "opt-withdraw":
        intent = "discuss_possible_withdrawal"
    if not intent:
        intent = detect_intent(transcript)

    selected_account = by_id.get(context.get("selected_account_id") or "")
    base = {
        "candidate_intent": intent,
        "selected_account_id": None,
        "definitions": [],
        "uncertainty": None,
        "question": None,
        "suggestions": [],
        "proposed_plain_language_request": None,
    }

    # Client asked for a person: stop asking questions; hand off with what we have.
    if selected_option_id == OPTION_TALK_TO_PERSON:
        base.update(
            proposed_plain_language_request=(
                f"I would like to talk with a person about this: \"{transcript.strip()}\"" if transcript.strip() else "I would like to talk with a person."
            ),
            uncertainty="The client asked to talk with a person. Remaining details will be gathered by staff.",
            definitions=_definitions(tools, ["advisor"]),
        )
        return base

    # Account not yet confirmed by the client.
    if not selected_account:
        if selected_option_id == OPTION_NONE_OF_THESE:
            remaining = [a for a in accounts if a["account_id"] not in offered]
            suggestions = [
                {"id": f"opt-acct-{a['account_id']}", "label": f"My {_mine(a)}", "account_id": a["account_id"]}
                for a in remaining[:2]
            ]
            suggestions.append({"id": "opt-other", "label": "Something else; I will describe it", "account_id": None})
            base.update(
                suggestions=suggestions[:3],
                question="No problem. Could you tell me a little more about which account you mean, or what you would like help with?",
                uncertainty="The client rejected the earlier suggestions; the account is still unresolved.",
                definitions=_definitions(tools, ["advisor"]),
            )
            return base

        relevant = [a for a in accounts if a.get("relevance", 0) > 0]
        candidate: dict[str, Any] | None = None
        if missing_types:
            # e.g. client said "Roth" but owns no Roth IRA.
            missing_label = _type_label(missing_types[0])
            retirement = [a for a in accounts if a.get("account_type") in RETIREMENT_TYPES]
            rollovers = [a for a in retirement if a.get("account_type") == "rollover_ira"]
            if former_employer and rollovers:
                candidate = rollovers[0]
            elif relevant:
                candidate = relevant[0]
            elif retirement:
                candidate = retirement[0]
            if candidate:
                via = " from your former employer" if candidate.get("account_type") == "rollover_ira" else ""
                question = (
                    f"I don't see a {missing_label} in these records. Could you mean your "
                    f"{_type_label(candidate.get('account_type'))}{via} ({candidate.get('masked_identifier')})?"
                )
                suggestions = [{"id": "opt-1", "label": f"Yes, my {_mine(candidate)}", "account_id": candidate["account_id"]}]
                others = [a for a in accounts if a["account_id"] != candidate["account_id"] and a.get("account_type") in RETIREMENT_TYPES]
                for other in others[:1]:
                    suggestions.append({"id": f"opt-{len(suggestions) + 1}", "label": f"No, my {_mine(other)}", "account_id": other["account_id"]})
                suggestions.append({"id": f"opt-{len(suggestions) + 1}", "label": "A different account or something else", "account_id": None})
                base.update(
                    suggestions=suggestions[:3],
                    question=question,
                    uncertainty=(
                        f"The client said '{missing_label}', but no {missing_label} appears in the authorized account list. "
                        f"The {_type_label(candidate.get('account_type'))} ({candidate.get('masked_identifier')}) is the closest match and needs the client's confirmation."
                    ),
                    definitions=_definitions(tools, [missing_label, _type_label(candidate.get("account_type"))] + _intent_terms(intent)),
                )
                return base
            base.update(
                question=f"I don't see a {missing_label} in these records. Which account would you like help with?",
                suggestions=[{"id": f"opt-acct-{a['account_id']}", "label": f"My {_mine(a)}", "account_id": a["account_id"]} for a in accounts[:2]]
                + [{"id": "opt-other", "label": "Something else; I will describe it", "account_id": None}],
                uncertainty=f"No {missing_label} appears in the authorized account list.",
                definitions=_definitions(tools, [missing_label]),
            )
            return base

        if len(relevant) == 1 or (relevant and relevant[0]["relevance"] > relevant[1]["relevance"]):
            candidate = relevant[0]
            base["selected_account_id"] = candidate["account_id"]  # proposal only; backend treats as candidate
            if intent == "discuss_possible_withdrawal":
                base.update(
                    suggestions=[
                        {"id": "opt-withdraw", "label": f"Discuss taking {_amount_phrase(transcript)}out of my {_short(candidate)}", "account_id": candidate["account_id"]},
                        {"id": "opt-options", "label": f"First understand my options for my {_short(candidate)}", "account_id": candidate["account_id"]},
                        {"id": "opt-other", "label": "A different account or something else", "account_id": None},
                    ],
                    question=f"Do you want to discuss taking money out of your {_short(candidate)}, or would you like to understand your options first?",
                    uncertainty="Account appears to match the client's words but has not been confirmed by the client. Amount is the client's stated figure, not verified.",
                    definitions=_definitions(tools, [_type_label(candidate.get("account_type"))] + _intent_terms(intent)),
                )
                return base
            base.update(
                suggestions=[
                    {"id": "opt-1", "label": _interpretation(intent, candidate), "account_id": candidate["account_id"]},
                    {"id": "opt-2", "label": f"Something else about my {_short(candidate)}", "account_id": candidate["account_id"]},
                    {"id": "opt-3", "label": "A different account", "account_id": None},
                ],
                question=None,
                uncertainty="Account appears to match the client's words but has not been confirmed by the client.",
                definitions=_definitions(tools, [_type_label(candidate.get("account_type"))] + _intent_terms(intent)),
                proposed_plain_language_request=_proposed_request(intent, candidate, transcript),
            )
            return base

        if len(relevant) >= 2:
            top = relevant[:2]
            base.update(
                suggestions=[{"id": f"opt-{i + 1}", "label": f"My {_mine(a)}", "account_id": a["account_id"]} for i, a in enumerate(top)]
                + [{"id": "opt-3", "label": "A different account or something else", "account_id": None}],
                question="Which account do you mean?",
                uncertainty="More than one account matches the client's words.",
                definitions=_definitions(tools, [_type_label(a.get("account_type")) for a in top] + _intent_terms(intent)),
            )
            return base

        # Nothing matched: ask which account, offering up to two owned accounts.
        if accounts and intent != "general_question":
            base.update(
                suggestions=[{"id": f"opt-{i + 1}", "label": f"My {_mine(a)}", "account_id": a["account_id"]} for i, a in enumerate(accounts[:2])]
                + [{"id": "opt-3", "label": "This is not about a specific account", "account_id": None}],
                question="Which account is this about?",
                uncertainty="The client's words did not name an account.",
                definitions=_definitions(tools, _intent_terms(intent) or ["advisor"]),
            )
            return base
        base.update(
            suggestions=[
                {"id": "opt-1", "label": "I have a question about one of my accounts", "account_id": None},
                {"id": "opt-2", "label": "I want to talk with my advisor about planning", "account_id": None},
                {"id": "opt-3", "label": "Something else", "account_id": None},
            ],
            question="Could you tell me a bit more about what you need help with?",
            uncertainty="The request is too general to interpret yet.",
            definitions=_definitions(tools, ["advisor"]),
        )
        return base

    # Account confirmed by the client. Clarify withdrawal vs. understanding options once.
    base["selected_account_id"] = selected_account["account_id"]
    if intent == "discuss_possible_withdrawal" and selected_option_id not in {"opt-withdraw", "opt-options"} and last_selected.get("id") not in {"opt-withdraw", "opt-options"}:
        base.update(
            suggestions=[
                {"id": "opt-withdraw", "label": f"Discuss taking {_amount_phrase(transcript)}out of my {_short(selected_account)}", "account_id": selected_account["account_id"]},
                {"id": "opt-options", "label": f"First understand my options for my {_short(selected_account)}", "account_id": selected_account["account_id"]},
            ],
            question=f"Do you want to discuss taking money out of your {_short(selected_account)}, or would you like to understand your options first?",
            uncertainty="Amount is the client's stated figure and has not been confirmed on the review screen.",
            definitions=_definitions(tools, [_type_label(selected_account.get("account_type")), "withdrawal"]),
        )
        return base

    base.update(
        proposed_plain_language_request=_proposed_request(intent, selected_account, transcript),
        uncertainty=None if intent != "discuss_possible_withdrawal" else "Amount and timing need the client's confirmation on the review screen.",
        definitions=_definitions(tools, [_type_label(selected_account.get("account_type"))] + _intent_terms(intent)),
    )
    return base


def _staff_summary(intent: str, account: dict[str, Any] | None, cr: dict[str, Any]) -> str:
    amount = cr.get("amount_requested")
    amount_phrase = f"${amount:,.0f} " if isinstance(amount, (int, float)) and float(amount).is_integer() else (f"${amount:,.2f} " if isinstance(amount, (int, float)) else "")
    acct = f"{_type_label(account.get('account_type'))} ({account.get('masked_identifier')})" if account else "an account not yet identified"
    purpose = _third_person(_purpose(cr.get("original_words", "")))
    purpose_note = f"{purpose} expenses" if purpose and "care" in purpose else purpose
    templates = {
        "discuss_possible_withdrawal": f"Client requests discussion of a possible {amount_phrase}distribution from {acct}{purpose_note}. Description of the question, not advice to transact.",
        "understand_options": f"Client requests an overview of options for {acct}; no transaction requested.",
        "update_beneficiary": f"Client requests a beneficiary designation change on {acct}.",
        "report_security_concern": f"Client reports possible unauthorized activity on {acct}; specialist security review recommended before any advisor contact.",
        "discuss_rollover_or_transfer": f"Client requests discussion of a possible rollover or transfer involving {acct}.",
        "discuss_required_minimum_distribution": f"Client requests information about required minimum distributions from {acct}.",
        "contribution_question": f"Client asks about contribution rules for {acct}.",
        "investment_planning_question": f"Client requests an investment planning discussion regarding {acct}.",
    }
    return templates.get(intent, f"Client request needs staff review to determine the service need: \"{cr.get('confirmed_plain_language_request', '')}\"")


def _unresolved(intent: str, cr: dict[str, Any]) -> list[str]:
    questions = {
        "discuss_possible_withdrawal": ["Desired timing of the distribution", "Potential tax implications for advisor review"],
        "understand_options": ["Which options the client wants to compare"],
        "update_beneficiary": ["New beneficiary details and relationship", "Whether the change should apply to other accounts"],
        "report_security_concern": ["Which transactions or logins the client did not authorize", "Whether credentials were shared or changed"],
        "discuss_rollover_or_transfer": ["Source and destination accounts", "Desired timing"],
        "discuss_required_minimum_distribution": ["Which accounts are subject to required minimum distribution rules"],
        "contribution_question": ["Tax year and amount the client has in mind"],
        "investment_planning_question": ["Specific holdings or goals the client wants to discuss"],
    }.get(intent, ["Specific service need"])
    if intent == "discuss_possible_withdrawal" and cr.get("amount_requested") is None:
        questions = ["Amount requested (not stated or not confirmed)"] + questions
    if not cr.get("selected_account"):
        questions = ["Which account the request concerns"] + questions
    return questions


def triage_case(confirmed_request: dict[str, Any], tools: Any) -> dict[str, Any]:
    cr = confirmed_request
    account = cr.get("selected_account")
    words = f"{cr.get('original_words', '')} {cr.get('confirmed_plain_language_request', '')}"
    intent = cr.get("candidate_intent") or detect_intent(words)
    if detect_security_concern(words):
        intent = "report_security_concern"
    categories = list(INTENT_CATEGORIES.get(intent, ["other_or_unclear"]))
    if account and account.get("account_type") not in RETIREMENT_TYPES:
        categories = [c for c in categories if c != "retirement_income"] or ["account_service"]
        if intent == "understand_options":
            categories = ["investment_planning"]
    if intent == "discuss_possible_withdrawal" and account and account.get("account_type") not in RETIREMENT_TYPES:
        categories = ["withdrawal_or_distribution", "account_service"]

    flags: list[str] = []
    if cr.get("missing_account_types"):
        flags.append("client_term_did_not_match_account_type")
    if intent == "report_security_concern":
        flags.append("possible_unauthorized_access")
    if cr.get("client_requested_person"):
        flags.append("client_requested_human_help")
    if not account:
        flags.append("account_unresolved")

    if account:
        tools["get_relevant_account_history"](account["account_id"])  # history is for staff view; model notes nothing from it

    directory = tools["search_advisor_directory"](categories, {"security_concern": intent == "report_security_concern"})
    urgency = {"level": "elevated", "reason": "Possible unauthorized access or fraud reported by the client."} if intent == "report_security_concern" else {"level": "none", "reason": None}

    return {
        "client_summary": cr.get("confirmed_plain_language_request"),
        "staff_summary": _staff_summary(intent, account, cr),
        "intent": intent,
        "categories": categories,
        "unresolved_questions": _unresolved(intent, cr),
        "flags": flags,
        "urgency": urgency,
        "recommended_destination": directory.get("destination"),
        "recommended_advisor_ids": [c["advisor_id"] for c in directory.get("candidates", [])],
    }
