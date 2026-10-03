"""Pydantic models for the SamePage version-one HTTP contract (Agent 2).

Field names follow ``contracts/API_V1.md`` and ``contracts/demo_fixture_v1.json``.
Fields marked "additive" are extra, backwards-compatible fields that the UI
agents may use (several are the optional version-two fields proposed in
``data/CONTRACT_V2_PROPOSAL.md``). Never rename or remove a contract field here.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# --------------------------------------------------------------------------
# Fixed vocabularies
# --------------------------------------------------------------------------

CATEGORY_TAXONOMY: tuple[str, ...] = (
    "retirement_income",
    "withdrawal_or_distribution",
    "rollover_or_transfer",
    "beneficiary_or_estate",
    "investment_planning",
    "account_service",
    "fraud_or_security",
    "other_or_unclear",
)

SESSION_STATUSES: tuple[str, ...] = ("draft", "needs_clarification", "ready_for_client_review", "submitted")
CASE_STATUSES: tuple[str, ...] = ("submitted", "staff_review", "assigned", "needs_client_followup")

ACCOUNT_MATCH_STATUSES: tuple[str, ...] = (
    "client_confirmed",   # client confirmed an account the agent proposed
    "client_selected",    # client chose an owned account the agent had not proposed
    "unresolved",         # no account selected; staff must resolve
    "not_needed",         # security/access concern with no single account involved
)

# Routing destinations. Names match the frozen fixture and Agent 4's seed cases.
SECURITY_DESTINATION = "security_specialist_review"
DESTINATIONS: dict[str, str] = {
    SECURITY_DESTINATION: "Security specialist review queue",
    "retirement_advisor_review": "Retirement and distribution advisor review",
    "estate_and_beneficiary_review": "Beneficiary and estate advisor review",
    "advisor_review": "Advisor review",
}
CATEGORY_TO_DESTINATION: dict[str, str] = {
    "fraud_or_security": SECURITY_DESTINATION,
    "retirement_income": "retirement_advisor_review",
    "withdrawal_or_distribution": "retirement_advisor_review",
    "rollover_or_transfer": "retirement_advisor_review",
    "beneficiary_or_estate": "estate_and_beneficiary_review",
    "investment_planning": "advisor_review",
    "account_service": "advisor_review",
    "other_or_unclear": "advisor_review",
}

# Reserved option ids a client UI may send in ``selected_option_id``.
OPTION_NONE_OF_THESE = "none_of_these"
OPTION_TALK_TO_PERSON = "talk_to_person"
RESERVED_OPTION_IDS: tuple[str, ...] = (OPTION_NONE_OF_THESE, OPTION_TALK_TO_PERSON)

MAX_SUGGESTIONS = 3
MAX_TEXT_CHARS = 4000
MAX_AMOUNT = 10_000_000

CONFIRM_CLIENT_SUMMARY_DEFAULT = "Your request has been sent for staff review."


def normalize_input_mode(value: str | None) -> str:
    raw = (value or "text").strip().lower()
    if raw in {"voice", "speech", "microphone", "mic", "spoken"}:
        return "voice"
    if raw in {"text", "typed", "keyboard", "type"}:
        return "text"
    return raw[:32] or "text"


# --------------------------------------------------------------------------
# Shared shapes
# --------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    details: Any | None = None


class Suggestion(BaseModel):
    id: str
    label: str
    account_id: str | None = None


class Definition(BaseModel):
    term: str
    plain: str


# --------------------------------------------------------------------------
# Intake
# --------------------------------------------------------------------------


class IntakeStartRequest(BaseModel):
    client_id: str = Field(min_length=1, max_length=64)


class IntakeStartResponse(BaseModel):
    session_id: str
    client_display_name: str
    status: str
    # additive
    client_id: str
    ai_mode: str
    simulated_access_control: bool = True


class IntakeTurnRequest(BaseModel):
    text: str = Field(default="", max_length=MAX_TEXT_CHARS)
    input_mode: str = Field(default="text", max_length=32)
    selected_option_id: str | None = Field(default=None, max_length=128)

    @field_validator("input_mode")
    @classmethod
    def _normalize_mode(cls, value: str) -> str:
        return normalize_input_mode(value)


class IntakeTurnResponse(BaseModel):
    session_id: str
    transcript: str
    suggestions: list[Suggestion] = Field(default_factory=list, max_length=MAX_SUGGESTIONS)
    question: str | None = None
    definitions: list[Definition] = Field(default_factory=list)
    candidate_intent: str | None = None
    selected_account_id: str | None = None
    uncertainty: str | None = None
    status: str
    # additive
    candidate_account_id: str | None = None
    proposed_plain_language_request: str | None = None
    message: str | None = None
    degraded: bool = False
    turn_number: int = 0


class IntakeConfirmRequest(BaseModel):
    confirmed_plain_language_request: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)
    selected_account_id: str | None = Field(default=None, max_length=64)
    amount_requested: float | None = Field(default=None, gt=0, le=MAX_AMOUNT)

    @field_validator("amount_requested", mode="before")
    @classmethod
    def _amount_must_be_a_number(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("amount_requested must be a number, not a boolean")
        if isinstance(value, str):
            cleaned = value.replace(",", "").replace("$", "").strip()
            if not cleaned:
                return None
            try:
                return float(cleaned)
            except ValueError as exc:
                raise ValueError("amount_requested must be a number") from exc
        return value


class IntakeConfirmResponse(BaseModel):
    case_id: str
    status: str
    client_summary: str
    # additive
    next_step: str


# --------------------------------------------------------------------------
# Case record (GET /staff/cases/{case_id})
# --------------------------------------------------------------------------


class RelevantEvent(BaseModel):
    type: str
    date: str
    source_id: str
    summary: str | None = None      # version-two optional field read by the staff page
    description: str | None = None  # same text; kept for earlier consumers


class AccountContext(BaseModel):
    account_type: str
    masked_identifier: str
    balance: int | float | None = None
    balance_as_of: str | None = None
    account_source_id: str | None = None
    relevant_events: list[RelevantEvent] = Field(default_factory=list)
    # additive / version-two optional
    account_id: str | None = None
    familiar_label: str | None = None
    account_label: str | None = None
    currency: str | None = "USD"
    ownership: str | None = None
    source_id: str | None = None
    cautions: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class Conflict(BaseModel):
    statement: str
    source_id: str | None = None


class StaffDecisionDetail(BaseModel):
    advisor_id: str
    staff_reason: str
    decided_at: str
    decided_by: str = "staff-demo"


class Routing(BaseModel):
    destination: str
    recommended_advisor_ids: list[str] = Field(default_factory=list)
    assigned_advisor_id: str | None = None
    staff_decision: str | None = None  # the staff member's recorded reason (string, as the mock/UI expect)
    # additive / version-two optional
    reason: str | None = None
    staff_decision_detail: StaffDecisionDetail | None = None
    model_recommended_advisor_ids: list[str] = Field(default_factory=list)
    model_routing_hint: str | None = None


class Urgency(BaseModel):
    level: Literal["none", "elevated"] = "none"
    reason: str | None = None


class ConversationTurn(BaseModel):
    turn_number: int
    text: str
    input_mode: str
    selected_option_id: str | None = None
    selected_option_label: str | None = None
    suggestions: list[Suggestion] = Field(default_factory=list)
    question: str | None = None
    uncertainty: str | None = None
    candidate_intent: str | None = None
    candidate_account_id: str | None = None
    degraded: bool = False
    at: str


class HistoryEntry(BaseModel):
    event: str
    at: str
    details: dict[str, Any] = Field(default_factory=dict)


class TriageInfo(BaseModel):
    status: Literal["completed", "failed", "seeded"]
    adapter: str
    error: str | None = None
    validation_notes: list[str] = Field(default_factory=list)


class CaseRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # contract (contracts/API_V1.md required fields)
    case_id: str
    client_id: str
    client_display_name: str
    created_at: str
    status: str
    input_mode: str
    original_words: str
    confirmed_plain_language_request: str
    staff_summary: str
    intent: str | None = None
    amount_requested: int | float | None = None
    currency: str | None = None
    selected_account_id: str | None = None
    account_match_status: str
    categories: list[str]
    unresolved_questions: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    account_context: AccountContext | None = None
    routing: Routing

    # additive / version-two optional
    preferred_contact_channel: str | None = None
    client_confirmed_at: str | None = None
    updated_at: str | None = None
    conflicts: list[Conflict] = Field(default_factory=list)
    urgency: Urgency = Field(default_factory=Urgency)
    existing_advisor_id: str | None = None
    conversation: list[ConversationTurn] = Field(default_factory=list)
    history: list[HistoryEntry] = Field(default_factory=list)
    triage: TriageInfo


# --------------------------------------------------------------------------
# Staff
# --------------------------------------------------------------------------


class QueueRouting(BaseModel):
    destination: str
    assigned_advisor_id: str | None = None


class StaffCaseSummary(BaseModel):
    case_id: str
    client_display_name: str
    created_at: str
    status: str
    categories: list[str]
    flags: list[str]
    confirmed_plain_language_request: str
    # additive
    client_id: str
    urgency: Urgency
    clarification_needed: bool
    existing_advisor_id: str | None = None
    routing: QueueRouting
    priority: dict[str, Any] = Field(default_factory=dict)  # {level, rank, reason}
    lifecycle: str = "new"


class StaffCasesResponse(BaseModel):
    cases: list[StaffCaseSummary]


class Candidate(BaseModel):
    advisor_id: str
    display_name: str
    specialties: list[str]
    available: bool
    reason: str
    # additive / version-two optional
    existing_client_relationship: bool = False
    meeting_mode: list[str] = Field(default_factory=list)
    capacity: int | None = None
    rank: int = 0
    active: bool = True
    region: str | None = None
    kind: str = "advisor"
    eligibility_check: str = "manual_verification_required"


class CandidatesResponse(BaseModel):
    candidates: list[Candidate]
    # additive
    case_id: str
    destination: str
    reason: str | None = None


class AssignRequest(BaseModel):
    advisor_id: str = Field(min_length=1, max_length=64)
    staff_reason: str = Field(min_length=1, max_length=2000)


class AssignResponse(BaseModel):
    case_id: str
    status: str
    assigned_advisor_id: str
    # additive
    flags: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Non-contract helpers (additive endpoints)
# --------------------------------------------------------------------------


class DemoClient(BaseModel):
    client_id: str
    display_name: str
    demo_scenario: str | None = None


class DemoClientsResponse(BaseModel):
    clients: list[DemoClient]
    simulated_access_control: bool = True


class HealthResponse(BaseModel):
    status: str
    ai_mode: str
    adapter: str
    live_model: bool
    data_source: str
    counts: dict[str, int]
    simulated_access_control: bool = True


class ResetResponse(BaseModel):
    status: str
    data_source: str
    counts: dict[str, int]
    server_restart_required: bool = False
