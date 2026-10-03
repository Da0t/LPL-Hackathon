# SamePage Version One Integration Contract

This contract is frozen for the four parallel development branches. Every agent can start from this file, `demo_fixture_v1.json`, and `mock_api.py` without waiting for another agent's code. `SAMEPAGE_PRODUCT_SPEC.md` explains the product; this file fixes the data exchanged between components. Do not change version-one field names on an individual branch. Propose a version-two change to the team if the contract is genuinely insufficient.

## Local development

The real app will serve client and staff pages plus the API from `http://localhost:8000`. Until that backend exists, run `python3 contracts/mock_api.py` to serve the same API at `http://localhost:8001`. Frontend code should read `window.SAMEPAGE_API_BASE` when present and otherwise use the same origin. The mock server uses only fictional data and must never be used as the judged AI demo.

The demo role is passed as `X-Demo-Role: client` or `X-Demo-Role: staff`. Client calls also pass `X-Demo-Client-Id: CLIENT-017`. This is a **simulation**, not real authentication. Agent 2 must enforce these roles in the local API and never describe them as production security.

All JSON responses use UTF-8. Errors use `{ "error_code": "CODE", "message": "Human-readable explanation" }` with an appropriate HTTP status. Unknown accounts, clients, advisors, and cases must return an error rather than invented values.

## Client endpoints

### POST /intake/start

Request: `{ "client_id": "CLIENT-017" }`

Response:

```json
{"session_id":"SESSION-001","client_display_name":"Mara Ellis","status":"draft"}
```

### POST /intake/{session_id}/turn

Request: `{ "text": "I need six thousand dollars from the Roth thing from my old job.", "input_mode": "text", "selected_option_id": null }`

Response:

```json
{
  "session_id": "SESSION-001",
  "transcript": "I need six thousand dollars from the Roth thing from my old job.",
  "suggestions": [{"id":"ACCT-201","label":"Retirement account from your former job","account_id":"ACCT-201"}],
  "question": "I don't see a Roth IRA here. Could you mean your rollover IRA from your former employer?",
  "definitions": [{"term":"rollover IRA","plain":"A retirement account that holds money moved from an earlier workplace retirement plan."}],
  "candidate_intent": "discuss_possible_withdrawal",
  "selected_account_id": null,
  "uncertainty": "Client said Roth IRA; the authorized account list shows a rollover IRA instead.",
  "status": "needs_clarification"
}
```

`input_mode` is `text` or `voice`. Send a stable phrase rather than every keystroke. The `text` field contains the current complete request as edited by the client. The response contains at most three suggestions; the frontend adds “None of these” and “Talk to a person.” On a later turn, setting `selected_option_id` to a returned suggestion ID can move status to `ready_for_client_review`. The user may also keep typing or reject suggestions. Null is valid for any unresolved account or question.

### POST /intake/{session_id}/confirm

Request:

```json
{"confirmed_plain_language_request":"I want to speak with an advisor about using $6,000 from my retirement account from my former employer.","selected_account_id":"ACCT-201","amount_requested":6000}
```

Response: `{ "case_id": "CASE-1043", "status": "submitted", "client_summary": "Your request has been sent for staff review." }`

Confirmation requires an explicit client action. The backend validates that a selected account belongs to the session's client. An amount must be explicitly entered or confirmed; the model cannot fill one silently.

## Staff endpoints

### GET /staff/cases

Response: `{ "cases": [{ "case_id": "CASE-1042", "client_display_name": "Mara Ellis", "created_at": "2026-10-02T20:00:00Z", "status": "submitted", "categories": ["withdrawal_or_distribution", "retirement_income"], "flags": ["client_term_did_not_match_account_type"], "confirmed_plain_language_request": "I want to speak with an advisor about using $6,000 from my retirement account from my former employer." }] }`

### GET /staff/cases/{case_id}

Response is the full case object in `demo_fixture_v1.json`. The required fields are `case_id`, `client_id`, `client_display_name`, `created_at`, `status`, `input_mode`, `original_words`, `confirmed_plain_language_request`, `staff_summary`, `intent`, `amount_requested`, `currency`, `selected_account_id`, `account_match_status`, `categories`, `unresolved_questions`, `flags`, `account_context`, and `routing`. `account_context` includes a balance **as-of date** and source IDs for relevant events.

### GET /staff/cases/{case_id}/candidates

Response:

```json
{"candidates":[{"advisor_id":"ADV-03","display_name":"Jordan Lee","specialties":["retirement_income","withdrawal_or_distribution"],"available":true,"reason":"Retirement-income specialty and available for a new case."}]}
```

For a `fraud_or_security` case, this endpoint may return an empty candidate list while `routing.destination` indicates specialist review.

### POST /staff/cases/{case_id}/assign

Request: `{ "advisor_id": "ADV-03", "staff_reason": "Retirement-income specialty and available." }`

Response: `{ "case_id": "CASE-1042", "status": "assigned", "assigned_advisor_id": "ADV-03" }`

Only staff can assign, and an assignment must include a reason. The mock changes its in-memory state; the real backend persists it. No message is sent to a real advisor.

## AI adapter interface

Agent 1 exports `intake_turn(client_id, transcript, selected_option_id, tools) -> dict` and `triage_case(confirmed_request, tools) -> dict`. Agent 2 provides the `tools` object and validates outputs. Agent 1 owns Bedrock calls; Agent 2 owns authorized account lookup, glossary lookup, history lookup, case state, and deterministic routing. The intake result matches the fields used by the `/turn` response except session and status, which Agent 2 supplies. The triage result supplies client and staff summaries, intent, categories, unresolved questions, and flags; Agent 2 attaches verified account facts and staff candidates.

Category values are `retirement_income`, `withdrawal_or_distribution`, `rollover_or_transfer`, `beneficiary_or_estate`, `investment_planning`, `account_service`, `fraud_or_security`, and `other_or_unclear`. Case statuses are `draft`, `needs_clarification`, `ready_for_client_review`, `submitted`, `staff_review`, `needs_client_followup`, and `assigned`.

## Fixture policy

`demo_fixture_v1.json` is the fixed integration fixture. Its `CLIENT-017`, `ACCT-201`, `ADV-03`, and `CASE-1042` IDs will not change. Agent 4 can create richer `data/*.json` files by copying and extending it, but must preserve those IDs and field meanings. Agent 2 can import the fixture immediately. Agents 3 and 4 can test their pages against `mock_api.py` without waiting for Agent 2. Agent 1 can test tools against the fixture without waiting for Agent 2.
