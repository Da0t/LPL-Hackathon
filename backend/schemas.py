"""Pydantic models for the SamePage version-one HTTP contract (Agent 2).

Field names here are the frozen contract from ``SAMEPAGE_PRODUCT_SPEC.md``.
Fields marked "additive" are extra, backwards-compatible fields that UI agents
may use but are not required to. Never rename or remove a contract field here
without notifying Agents 1, 3, and 4.
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

SESSION_STATUSES: tuple[str, ...] = (
    "draft",
    "needs_clarification",
    "ready_for_client_review",
    "submitted",
)

CASE_STATUSES: tuple[str, ...] = (
    "submitted",
    "staff_review",
    "assigned",
    "needs_client_followup",
)

ACCOUNT_MATCH_STATUSES: tuple[str, ...] = (
    "client_confirmed",   # client confirmed the account the agent proposed
    "client_selected",    # client chose an owned account the agent had not proposed
    "unresolved",         # no account selected; staff must resolve
)

DESTINATIONS: dict[str, str] = {
    "specialist_security_review": "Security and fraud specialist review queue",
    "retirement_advisor_review": "Retirement and distribution advisor review",
    "estate_planning_advisor_review": "Beneficiary and estate advisor review",
    "investment_advisor_review": "Investment planning advisor review",
    "client_service_review": "Client service review",
    "general_advisor_review": "General advisor review",
}

CATEGORY_TO_DESTINATION: dict[str, str] = {
    "fraud_or_security": "specialist_security_review",
    "retirement_income": "retirement_advisor_review",
    "withdrawal_or_distribution": "retirement_advisor_review",
    "rollover_or_transfer": "retirement_advisor_review",
    "beneficiary_or_estate": "estate_planning_advisor_review",
    "investment_planning": "investment_advisor_review",
    "account_service": "client_service_review",
    "other_or_unclear": "general_advisor_review",
}

# Reserved option ids a client UI may send in ``selected_option_id``.
OPTION_NONE_OF_THESE = "none_of_these"
OPTION_TALK_TO_PERSON = "talk_to_person"
RESERVED_OPTION_IDS: tuple[str, ...] = (OPTION_NONE_OF_THESE, OPTION_TALK_TO_PERSON)

MAX_SUGGESTIONS = 3
MAX_TEXT_CHARS = 4000
MAX_AMOUNT = 10_000_000


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
    agent_mode: str
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
    description: str | None = None


class AccountContext(BaseModel):
    account_id: str
    account_type: str
    account_label: str
    masked_identifier: str
    ownership: str | None = None
    balance: int | float | None = None
    balance_as_of: str | None = None
    source_id: str | None = None
    relevant_events: list[RelevantEvent] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class StaffDecision(BaseModel):
    advisor_id: str
    staff_reason: str
    decided_at: str
    decided_by: str = "staff-demo"


class Routing(BaseModel):
    destination: str
    destination_reason: str | None = None
    recommended_advisor_ids: list[str] = Field(default_factory=list)
    assigned_advisor_id: str | None = None
    staff_decision: StaffDecision | None = None
    model_recommended_advisor_ids: list[str] = Field(default_factory=list)


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
    status: Literal["completed", "failed"]
    adapter: str
    error: str | None = None
    validation_notes: list[str] = Field(default_factory=list)


class CaseRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    client_id: str
    client_display_name: str
    preferred_contact_channel: str | None = None
    status: str
    input_mode: str
    created_at: str
    client_confirmed_at: str
    updated_at: str

    original_words: str
    confirmed_plain_language_request: str
    staff_summary: str
    intent: str | None = None

    amount_requested: int | float | None = None
    currency: str = "USD"
    selected_account_id: str | None = None
    account_match_status: str

    categories: list[str]
    unresolved_questions: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    urgency: Urgency = Field(default_factory=Urgency)

    account_context: AccountContext | None = None
    routing: Routing

    conversation: list[ConversationTurn] = Field(default_factory=list)
    history: list[HistoryEntry] = Field(default_factory=list)
    triage: TriageInfo
    existing_advisor_id: str | None = None


# --------------------------------------------------------------------------
# Staff
# --------------------------------------------------------------------------


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
    destination: str
    assigned_advisor_id: str | None = None


class StaffCasesResponse(BaseModel):
    cases: list[StaffCaseSummary]


class Candidate(BaseModel):
    advisor_id: str
    display_name: str
    specialties: list[str]
    available: bool
    reason: str
    # additive
    rank: int
    existing_relationship: bool = False
    active: bool = True
    meeting_modes: list[str] = Field(default_factory=list)
    capacity: int | None = None
    region: str | None = None
    kind: str = "advisor"
    eligibility_check: str = "manual_verification_required"


class CandidatesResponse(BaseModel):
    candidates: list[Candidate]
    # additive
    case_id: str
    destination: str
    destination_reason: str | None = None


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
    agent_mode: str
    agent_adapter: str
    data_source: str
    counts: dict[str, int]
    simulated_access_control: bool = True


class ResetResponse(BaseModel):
    status: str
    data_source: str
    counts: dict[str, int]
