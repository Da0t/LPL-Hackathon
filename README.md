# SamePage

SamePage helps a client describe a financial service need in everyday words, verify which account they
mean, and send a confirmed request to the right person. A client can say "the retirement money from my
old job" and reach the right advisor without guessing which account they meant.

This repository is the LPL hackathon prototype built by four parallel agents. This README covers the
**backend (Agent 2)**: the FastAPI app that implements the frozen version-one contract, local SQLite
storage, the authorized tool callbacks given to the language model, deterministic routing, and tests.

- Frozen contract: [`contracts/API_V1.md`](contracts/API_V1.md) with the fixture
  [`contracts/demo_fixture_v1.json`](contracts/demo_fixture_v1.json)
- Launch and acceptance steps: [`INTEGRATION_RUNBOOK.md`](INTEGRATION_RUNBOOK.md)
- Generated request/response examples from a real run: [`docs/API_EXAMPLES.md`](docs/API_EXAMPLES.md)
- Product spec: [`SAMEPAGE_PRODUCT_SPEC.md`](SAMEPAGE_PRODUCT_SPEC.md); briefs: [`agent-briefs/`](agent-briefs/)

All data is synthetic. The demo role switcher is **simulated access control**, not production
authentication. No message, transaction, appointment, or real LPL system call ever occurs.

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # FastAPI, Uvicorn, tests, and Agent 1's boto3 pins
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

`python -m backend.main` is equivalent. Open <http://127.0.0.1:8000/> for links to the client page
(`/client`, Agent 3), the staff page (`/staff`, Agent 4), interactive API docs (`/docs`), and
`/health`. If a page's files are not on disk yet the route shows a placeholder; the real files are
served as soon as they exist, no restart needed.

### The judged path: live Amazon Bedrock

```bash
export AWS_REGION=us-east-1
export BEDROCK_MODEL_ID=<verified allowlisted model id>   # see AWS_SETUP.md (Agent 1)
export SAMEPAGE_AI_MODE=bedrock
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

`SAMEPAGE_AI_MODE=bedrock` imports Agent 1's `backend/aws/bedrock_agent.py` and **fails fast at
startup** if it cannot, so the judged demo never silently runs on a mock. The landing page and
`/health` (`live_model: true/false`) show which adapter is active. A model or AWS error at runtime
preserves the client's draft and returns the adapter's own message instead of a stack trace.

| `SAMEPAGE_AI_MODE` | Adapter | Use |
| --- | --- | --- |
| `bedrock` | Agent 1, live Bedrock | the judged demo |
| `stub` | Agent 1's module in its offline stub mode | checking the seam without AWS |
| `mock` (default) | Agent 2's deterministic mock | UI development and the test suite |

### Demo reset

```bash
python -m backend.reset_demo            # clears sessions, live cases, assignments; reloads seed data
# or, while the server runs:
curl -X POST -H 'X-Demo-Role: staff' http://127.0.0.1:8000/demo/reset
```

The server does **not** need to restart; it reads SQLite on every request. After a reset the staff
queue shows Agent 4's four seed cases (`CASE-1040`, `CASE-1041`, `CASE-1042`, `CASE-SEC-1`) and the
next live case is `CASE-1043`, as in the contract example.

### Tests and examples

```bash
python -m pytest                            # 50 offline tests: mock adapter, in-memory SQLite
python scripts/generate_api_examples.py     # regenerate docs/API_EXAMPLES.md from a real run
```

## Configuration (environment only; no credentials in code)

| Variable | Default | Meaning |
| --- | --- | --- |
| `SAMEPAGE_AI_MODE` | `mock` | `bedrock`, `stub`, or `mock` (see above). `SAMEPAGE_AGENT_MODE` is a legacy alias. |
| `AWS_REGION`, `BEDROCK_MODEL_ID` | | Read by Agent 1's adapter in `bedrock` mode (AWS_SETUP.md) |
| `SAMEPAGE_DB_PATH` | `var/samepage.db` | SQLite file; `:memory:` for ephemeral runs |
| `SAMEPAGE_DATA_DIR` | `data/` | Agent 4's seed files; falls back to `backend/fixtures/` when missing or incomplete |
| `SAMEPAGE_DEFAULT_DEMO_ROLE` | `client` | Role assumed when `X-Demo-Role` is absent (set `staff` while building the staff page) |
| `SAMEPAGE_ADAPTER_TIMEOUT_S` | `90` | Seconds before a model call is treated as failed and the draft is preserved |
| `SAMEPAGE_RESET_ON_START` | `false` | Reset state on every start (handy for rehearsals) |
| `SAMEPAGE_HOST` / `SAMEPAGE_PORT` | `127.0.0.1` / `8000` | Bind address for `python -m backend.main` |
| `SAMEPAGE_CLIENT_DIR` / `SAMEPAGE_STAFF_DIR` | `frontend/client`, `frontend/staff` | Static page directories |
| `SAMEPAGE_LOG_LEVEL` | `INFO` | Log verbosity for the app and Uvicorn |

## HTTP contract (version one, frozen in contracts/API_V1.md)

Exact paths and field names from the contract. Fields beyond it are additive and safe to ignore;
several are the optional version-two fields the staff page already reads
(`data/CONTRACT_V2_PROPOSAL.md`).

| Endpoint | Role | Request | Response |
| --- | --- | --- | --- |
| `POST /intake/start` | client | `{client_id}` | `{session_id, client_display_name, status}` + `client_id, ai_mode` |
| `POST /intake/{session_id}/turn` | client | `{text, input_mode, selected_option_id?}` | `{session_id, transcript, suggestions, question, definitions, candidate_intent, selected_account_id, uncertainty, status}` + `candidate_account_id, proposed_plain_language_request, message, degraded, turn_number` |
| `POST /intake/{session_id}/confirm` | client | `{confirmed_plain_language_request, selected_account_id?, amount_requested?}` | `{case_id, status, client_summary}` + `next_step` |
| `GET /staff/cases` | staff | optional `?status=`, `?category=` | `{cases: [{case_id, client_display_name, created_at, status, categories, flags, confirmed_plain_language_request}]}` + `client_id, urgency, clarification_needed, existing_advisor_id, routing{destination, assigned_advisor_id}` per row |
| `GET /staff/cases/{case_id}` | staff | | the fixture's case object (below) |
| `GET /staff/cases/{case_id}/candidates` | staff | | `{candidates: [{advisor_id, display_name, specialties, available, reason}]}` + per candidate `existing_client_relationship, meeting_mode, capacity, rank, eligibility_check`; top level `case_id, destination, reason` |
| `POST /staff/cases/{case_id}/assign` | staff | `{advisor_id, staff_reason}` | `{case_id, status, assigned_advisor_id}` + `flags` |

Helper endpoints (additive): `GET /health`, `GET /demo/clients` (for the role switcher),
`POST /demo/reset` (staff).

Errors are `{error_code, message}` plus `details` when useful, with the same codes as the
contract's mock where one exists: `WRONG_DEMO_ROLE` (403), `WRONG_DEMO_CLIENT` (403),
`INVALID_ROLE` (400), `CLIENT_NOT_FOUND` (404), `SESSION_NOT_FOUND` (404), `CASE_NOT_FOUND`
(404), `INVALID_TURN` (400), `INVALID_OPTION` (400, with `details.valid_option_ids`),
`ACCOUNT_MISMATCH` (403), `MISSING_CONFIRMATION` (400), `NOTHING_TO_CONFIRM` (409),
`SESSION_ALREADY_SUBMITTED` (409, with `details.case_id`), `INVALID_ASSIGNMENT` (400),
`ADVISOR_NOT_FOUND` (404), `ADVISOR_NOT_ACTIVE` (409), `INVALID_JSON` (400), `VALIDATION_ERROR`
(422), `PATH_NOT_FOUND` (404).

### Semantics the pages rely on

- **Demo role switcher.** `X-Demo-Role: client` plus `X-Demo-Client-Id` on `/intake/*`;
  `X-Demo-Role: staff` on `/staff/*` and `/demo/reset`. A `?demo_role=staff` query parameter also
  works for browser checks. A missing role header means `client`; a missing client header is allowed
  for curl, but a mismatched one is refused. Label it as simulated access control in the UI.
- **`text` is the whole edited transcript**, not just the newest phrase. Send `""` with a
  `selected_option_id` for a selection-only turn.
- **Suggestions are proposals.** `selected_account_id` becomes non-null only when the client picks a
  card that carries an `account_id` or chooses an account on the review screen (via `confirm`). The
  model's own guess is exposed separately as `candidate_account_id`. Suggestion ids are whatever the
  adapter returns (Agent 1 uses the account id); any id must be one shown on the previous turn.
- **Reserved option ids** (optional for the UI): `none_of_these` clears the proposed account and asks
  for other interpretations; `talk_to_person` stops questions and flags the case
  `client_requested_human_help`.
- **Statuses.** Session: `draft` -> `needs_clarification` | `ready_for_client_review` -> `submitted`.
  Case: `submitted` -> `staff_review` (set when staff opens the case) -> `assigned`. Confirming is
  allowed from either session state; unresolved questions travel to staff. The spec's
  `needs_client_followup` status is accepted in the vocabulary but version one has no endpoint that
  sets it (Agent 4's `CONTRACT_V2_PROPOSAL.md` lists this as a version-two need).
- **Confirmation.** Only the values sent in `confirm` are confirmed. An amount the client *said* but
  did not confirm is never inferred into the case; a confirmed amount that does not appear in the
  words is flagged `amount_not_in_transcript`. `client_summary` is the triage model's plain-language
  summary, or "Your request has been sent for staff review." when it gave none.
- **Degraded turns.** When the model or AWS fails, `/turn` returns `degraded: true`,
  `status: "needs_clarification"`, a `message` to display (Agent 1's own wording when it raised
  `BedrockAdapterError`), the preserved `transcript`, and the previous `suggestions`/`question`.
- **Security cases.** Possible fraud, unauthorized access, or account takeover (model category **or**
  deterministic keyword detection) gives `routing.destination: security_specialist_review`,
  `urgency.level: elevated`, `account_match_status: not_needed` when no account was chosen, and an
  empty `/candidates` list unless the directory has a `fraud_or_security` specialist. Staff may still
  assign anyone; overrides are recorded as flags.

### Case record (`GET /staff/cases/{case_id}`)

The fixture's case object with these conventions:

- `original_words` is the transcript exactly as the client left it; `confirmed_plain_language_request`
  is the wording the client approved; `staff_summary` is the triage model's financial-terminology
  description of the question, not advice. `currency` is `"USD"` when an amount was confirmed and
  `null` otherwise.
- `account_match_status`: `client_confirmed`, `client_selected` (an owned account the agent had not
  proposed), `unresolved`, or `not_needed` (security concern without a single account).
- `account_context` holds **only record-backed facts**: `account_type`, `masked_identifier`,
  `balance` with `balance_as_of` and `account_source_id`, and `relevant_events` (`type`, `date`,
  `source_id`, `summary`) filtered to the event types that explain the case's categories, plus
  `familiar_label`, `currency`, `cautions`, and `sources`. Anything the model returns about balances
  or history is discarded and noted in `triage.validation_notes`.
- `conflicts` is a list of sourced statements such as "Client said 'Roth IRA'; no Roth IRA appears in
  the authorized account list." with the account record as `source_id`.
- `routing`: `destination` (`security_specialist_review`, `retirement_advisor_review`,
  `estate_and_beneficiary_review`, or `advisor_review`), `reason`, `recommended_advisor_ids` (the
  deterministic ranking), `assigned_advisor_id`, `staff_decision` (the staff member's reason, a
  string), `staff_decision_detail`, and the model's own `model_recommended_advisor_ids` and
  `model_routing_hint` for comparison.
- Flags you may see: `client_term_did_not_match_account_type`, `security_keywords_detected`,
  `possible_unauthorized_access`, `amount_not_in_transcript`, `account_unresolved`,
  `account_selected_outside_suggestions`, `client_requested_human_help`, `triage_unavailable`,
  `staff_overrode_recommendation`, `staff_overrode_specialist_recommendation`.
- Also present: `preferred_contact_channel`, `client_confirmed_at`, `urgency`, `existing_advisor_id`,
  `conversation` (every turn), `history` (every state change), `triage` (adapter, status, notes).

## Deterministic rules (application code, not the model)

1. A session binds one synthetic client. Every lookup, suggestion, and confirmation is scoped to that
   client's accounts; another client's account id is refused (`ACCOUNT_MISMATCH`).
2. The model proposes; the client chooses. Accounts and amounts are confirmed only by explicit client
   action on the review screen.
3. A confirmed case retains the original words, the client-approved wording, the selected account or an
   unresolved marker, the staff summary, categories, flags, and source references.
4. Possible fraud, unauthorized access, or account takeover routes to the security specialist review
   queue, never directly to a general advisor. Staff decide.
5. Advisor ranking uses only the fictional directory, in the spec's order: the client's existing active
   advisor first, then availability, specialty match, meeting preference, and capacity. Inactive
   advisors never appear. License and state eligibility are never inferred; every candidate carries
   `eligibility_check: "manual_verification_required"`.
6. Model failures preserve the draft. `assign` records the staff member's advisor and reason and changes
   nothing outside this database.

## The seam to Agent 1 (language-model adapter)

The backend imports `backend.aws.bedrock_agent` in `bedrock`/`stub` mode and calls, under a timeout:

```python
intake_turn(client_id, transcript, selected_option_id, tools) -> dict
triage_case(confirmed_request, tools) -> dict
```

`tools` is a dict that also supports attribute access; callbacks accept keyword or positional
arguments and match AWS_SETUP.md §8:

| Callback | Returns |
| --- | --- |
| `get_relevant_accounts(client_id, phrase)` | `list[{account_id, account_type, familiar_label, masked_identifier, label, ownership, former_employer, matched_terms, relevance}]`, most relevant first, **no balances**; `[]` for another client |
| `get_approved_definition(term)` | `{term, plain, source_id?}` or `None` |
| `get_relevant_account_history(account_id)` | `list[{type, date, source_id, summary, description}]`; `[]` unless the account is the client's |
| `search_advisor_directory(categories, preferences)` | ranked `list[{advisor_id, display_name, specialties, available, reason, meeting_mode, capacity, existing_client_relationship, ...}]`; `[]` for security cases |
| `get_session_context()` (extra) | prior turns, questions asked, suggestions offered, selections made |

`confirmed_request` contains `case_id, client_id, client_display_name, original_words,
confirmed_plain_language_request, input_mode, selected_account_id, selected_account (public fields,
no balance), account_match_status, amount_requested, currency, candidate_intent,
conversation_notes, client_requested_person, authorized_account_types, mentioned_account_types,
missing_account_types`.

The backend validates every adapter result: suggestions are capped at three, unauthorized account
ids are stripped, definitions must be in the approved glossary (the approved text wins), categories
must be in the taxonomy, `routing_hint`/`recommended_destination` must be a known destination, and
any account facts are dropped. `BedrockAdapterError(code, message)` becomes a preserved draft with
that message. The seam was exercised against Agent 1's real module in stub mode (see
`tests/backend/test_rules.py::test_tools_match_agent1_seam_and_hide_balances`).

## Seed data (Agent 4)

The store loads `data/clients.json`, `accounts.json`, `events.json`, `advisors.json`, and
`glossary.json` when all five exist and parse, plus the optional `data/cases.json` queue seed and
`meta.specialist_queues` from the advisor file. Otherwise it uses `backend/fixtures/`, a verbatim
copy of Agent 4's files, and says so in `/health`. Files may be lists or `{meta, <name>: [...]}`
objects; common alternative field names (`id`, `name`, `type`, `last4`, `as_of`, `specialty_tags`,
`meeting_mode`, `definition`, `also_heard_as`, `summary`) are accepted. Fixed fixture ids
(`CLIENT-017`, `ACCT-201`, `ADV-03`, `CASE-1042`) are preserved.

## Layout

```
backend/
  main.py           app factory, error envelope, static pages, CLI entry (exposes `app`)
  api.py            the seven contract routes + health/demo helpers
  schemas.py        pydantic models, taxonomy, statuses, destinations
  store.py          SQLite repository + tolerant seed loader (clients, accounts, events, advisors, glossary, seed cases)
  settings.py       environment configuration
  reset_demo.py     demo reset CLI (reset.py is an alias)
  fixtures/         fallback copy of Agent 4's data/
  services/
    intake.py       session state machine (start / turn / confirm)
    triage.py       case builder: facts from records, flags, routing
    case_facts.py   account context, relevant events, sourced conflicts, seed-case normalization
    staff.py        queue, case document, candidates, assignment
    routing.py      deterministic destination + advisor ranking
    tools.py        authorized tool callbacks for the model
    validation.py   sanitizes adapter output
    mock_agent.py   offline adapter with Agent 1's signatures
    agent_adapter.py  loads mock / stub / bedrock, timeout, sync or async
    auth.py         demo role switcher (simulated access control)
    text_rules.py   security keywords, account-term mentions, amounts
  aws/              Agent 1 (Bedrock adapter, config, Transcribe)
frontend/client/    Agent 3     frontend/staff/   Agent 4     data/   Agent 4
contracts/          frozen contract, fixture, standalone mock (port 8001)
tests/backend/      contract, scenario, rule, store, and app tests
scripts/generate_api_examples.py
```

## What is live and what is simulated

- Live when `SAMEPAGE_AI_MODE=bedrock`: language interpretation, clarifying questions, triage summaries
  and categories (Amazon Bedrock through Agent 1's adapter).
- Always deterministic application code: authorization scope, account facts and sources, contradiction
  statements, security routing, advisor ranking, state transitions, assignment.
- Simulated: the demo role switcher, and every client, account, balance, event, and advisor.
