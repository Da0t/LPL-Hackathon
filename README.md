# SamePage

SamePage helps a client describe a financial service need in everyday words, verify which account they
mean, and send a confirmed request to the right person. A client can say "the retirement money from my
old job" and reach the right advisor without guessing which account they meant.

This repository is the LPL hackathon prototype built by four parallel agents. This README covers the
**backend (Agent 2)**: the FastAPI app, the version-one HTTP contract, local SQLite storage, the
authorized tool callbacks given to the language model, deterministic routing, and tests.

- Product spec and frozen API contract: [`SAMEPAGE_PRODUCT_SPEC.md`](SAMEPAGE_PRODUCT_SPEC.md)
- Generated request/response examples: [`docs/API_EXAMPLES.md`](docs/API_EXAMPLES.md)
- Team briefs: [`agent-briefs/`](agent-briefs/)

All data is synthetic. The demo role switcher is **simulated access control**, not production
authentication. No message, transaction, appointment, or real LPL system call ever occurs.

## One-command startup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m backend.main            # http://127.0.0.1:8000  (mock language model, offline)
```

Open <http://127.0.0.1:8000/> for links to the client page (`/client`), staff page (`/staff`),
interactive API docs (`/docs`), and `/health`. Until Agents 3 and 4 add their files under
`frontend/client/` and `frontend/staff/`, those routes show a placeholder page; the real files are
served as soon as they exist on disk, no restart needed.

### Live Bedrock mode (the judged path)

```bash
pip install -r requirements.txt -r requirements-aws.txt     # Agent 1's dependencies
export AWS_REGION=us-east-1                                   # plus Agent 1's model/credential setup, see AWS_SETUP.md
SAMEPAGE_AGENT_MODE=bedrock python -m backend.main
```

`bedrock` mode imports `backend/aws/bedrock_agent.py` (Agent 1) and **fails fast at startup** if it
cannot, so the judged demo never silently runs on the mock. `/health` and the landing page show which
adapter is active. A model or AWS error at runtime preserves the client's draft and returns a useful
message instead of a stack trace.

### Demo reset

```bash
python -m backend.reset                              # clears sessions, cases, assignments; reloads seed data
# or, while the server runs:
curl -X POST -H 'X-Demo-Role: staff' http://127.0.0.1:8000/demo/reset
```

### Tests

```bash
python -m pytest                 # offline; uses the mock adapter and in-memory SQLite
python scripts/generate_api_examples.py   # regenerate docs/API_EXAMPLES.md after a contract change
```

## Configuration (environment variables, no credentials in code)

| Variable | Default | Meaning |
| --- | --- | --- |
| `SAMEPAGE_AGENT_MODE` | `mock` | `mock` (offline, deterministic) or `bedrock` (Agent 1's live adapter) |
| `SAMEPAGE_DB_PATH` | `var/samepage.db` | SQLite file; `:memory:` for ephemeral runs |
| `SAMEPAGE_DATA_DIR` | `data/` | Agent 4's seed files; falls back to `backend/fixtures/` when missing or incomplete |
| `SAMEPAGE_DEFAULT_DEMO_ROLE` | `client` | Role assumed when `X-Demo-Role` is absent (set `staff` while building the staff page) |
| `SAMEPAGE_ADAPTER_TIMEOUT_S` | `45` | Seconds before a model call is treated as failed and the draft is preserved |
| `SAMEPAGE_RESET_ON_START` | `false` | Reset state every start (handy for rehearsals) |
| `SAMEPAGE_HOST` / `SAMEPAGE_PORT` | `127.0.0.1` / `8000` | Bind address for `python -m backend.main` |
| `SAMEPAGE_CLIENT_DIR` / `SAMEPAGE_STAFF_DIR` | `frontend/client`, `frontend/staff` | Static page directories |

## HTTP contract (version one, frozen)

Exact paths and field names from the product spec. Additive fields are extra and safe to ignore.

| Endpoint | Role | Request | Response |
| --- | --- | --- | --- |
| `POST /intake/start` | client | `{client_id}` | `{session_id, client_display_name, status}` + `client_id, agent_mode, simulated_access_control` |
| `POST /intake/{session_id}/turn` | client | `{text, input_mode, selected_option_id?}` | `{session_id, transcript, suggestions, question, definitions, candidate_intent, selected_account_id, uncertainty, status}` + `candidate_account_id, proposed_plain_language_request, message, degraded, turn_number` |
| `POST /intake/{session_id}/confirm` | client | `{confirmed_plain_language_request, selected_account_id?, amount_requested?}` | `{case_id, status, client_summary}` + `next_step` |
| `GET /staff/cases` | staff | optional `?status=`, `?category=` | `{cases: [{case_id, client_display_name, created_at, status, categories, flags, confirmed_plain_language_request, ...}]}` + `client_id, urgency, clarification_needed, existing_advisor_id, destination, assigned_advisor_id` per row |
| `GET /staff/cases/{case_id}` | staff | | full case record (spec example schema) + `conversation, history, triage, urgency, existing_advisor_id` |
| `GET /staff/cases/{case_id}/candidates` | staff | | `{candidates: [{advisor_id, display_name, specialties, available, reason, ...}]}` + `case_id, destination, destination_reason` |
| `POST /staff/cases/{case_id}/assign` | staff | `{advisor_id, staff_reason}` | `{case_id, status, assigned_advisor_id}` + `flags` |

Helper endpoints (additive): `GET /health`, `GET /demo/clients` (for the role switcher), `POST /demo/reset` (staff).

Errors use `{error_code, message}` and sometimes `details`. Codes you will meet: `forbidden` (403, wrong
demo role), `invalid_role` (400), `client_not_found` (404), `session_not_found` (404), `case_not_found`
(404), `empty_turn` (400), `invalid_option` (400, includes `details.valid_option_ids`),
`account_not_authorized` (403), `nothing_to_confirm` (409), `session_already_submitted` (409, includes
`details.case_id`), `advisor_not_found` (404), `advisor_not_active` (409), `staff_reason_required` (400),
`validation_error` (422).

### Semantics the UI agents need

- **Demo role switcher.** Send `X-Demo-Role: client` on `/intake/*` and `X-Demo-Role: staff` on
  `/staff/*`. A `?demo_role=staff` query parameter also works for quick browser checks. Missing header
  means `client`. Label it as simulated access control in the UI.
- **`text` is the whole editable transcript**, not just the newest phrase. The backend stores it as the
  client's original words. Send `""` with a `selected_option_id` for a selection-only turn.
- **Suggestions are proposals.** `selected_account_id` becomes non-null only when the client selects a
  card that carries an `account_id` (via `selected_option_id`) or chooses an account on the review
  screen (via `confirm`). The model's own guess is exposed separately as `candidate_account_id`.
- **Reserved option ids:** `none_of_these` (clears the proposed account and asks the model for other
  interpretations) and `talk_to_person` (stops questions; status becomes `ready_for_client_review`
  and the case is flagged `client_requested_human_help`). Any other id must be one shown on the
  previous turn, or the backend returns `invalid_option`.
- **Statuses.** Session: `draft` -> `needs_clarification` | `ready_for_client_review` -> `submitted`.
  Case: `submitted` -> `staff_review` (set when staff opens the case) -> `assigned`. Confirming is
  allowed from either `needs_clarification` or `ready_for_client_review`; unresolved questions travel
  to staff.
- **Review screen.** Show `proposed_plain_language_request` in "What we understood", the selected or
  candidate account's label and masked id in "Account we think you mean", and let the client edit all
  of it. Only the values sent in `confirm` are confirmed. An amount the client *said* but did not
  confirm is never inferred into the case; a confirmed amount that does not appear in the words is
  flagged `amount_not_in_transcript` for staff.
- **Degraded turns.** When the model or AWS fails, `/turn` returns `degraded: true`,
  `status: "needs_clarification"`, a `message` to display, the preserved `transcript`, and the previous
  `suggestions`/`question` so the client can continue, retry, or talk to a person.
- **Security cases.** When the request indicates possible fraud, unauthorized access, or account
  takeover, `routing.destination` is `specialist_security_review`, `urgency.level` is `elevated`, and
  `/candidates` lists only the specialist review desk. Staff may still assign anyone; overrides are
  recorded as flags (`staff_overrode_specialist_recommendation`, `staff_overrode_recommendation`).

### Case record

`GET /staff/cases/{case_id}` returns the spec's example schema with these conventions:

- `original_words` is the transcript exactly as the client left it; `confirmed_plain_language_request`
  is the wording the client approved; `staff_summary` is the triage model's financial-terminology
  description of the question (not advice).
- `account_match_status` is `client_confirmed` (client confirmed a proposed account), `client_selected`
  (client chose an owned account the agent had not proposed), or `unresolved`.
- `account_context` is present only when an account was selected and contains **only** record-backed
  facts: `balance` with `balance_as_of` and `source_id`, `relevant_events` each with `date` and
  `source_id`, `conflicts` such as "Client said 'Roth IRA'; no Roth IRA appears in the authorized
  account list.", standard `cautions`, and `sources`. Anything the model returns about balances or
  history is discarded and noted in `triage.validation_notes`.
- `flags` you may see: `client_term_did_not_match_account_type`, `security_keywords_detected`,
  `possible_unauthorized_access`, `amount_not_in_transcript`, `account_unresolved`,
  `account_selected_outside_suggestions`, `client_requested_human_help`, `triage_unavailable`, plus
  the staff override flags above.
- `routing.recommended_advisor_ids` is the deterministic ranking (see below); the model's own
  suggestion, if any, is kept separately in `routing.model_recommended_advisor_ids`.

## Deterministic rules (application code, not the model)

1. A session binds one synthetic client. Every lookup, suggestion, and confirmation is scoped to that
   client's accounts; a request for another client's account id returns `account_not_authorized`.
2. The model proposes; the client chooses. Accounts and amounts are confirmed only by explicit client
   action on the review screen.
3. A confirmed case retains the original words, the client-approved wording, the selected account or an
   unresolved marker, the staff summary, categories, flags, and source references.
4. Possible fraud, unauthorized access, or account takeover (model category **or** deterministic keyword
   detection) routes to the specialist review queue, never directly to a general advisor. Staff decides.
5. Advisor ranking uses only the fictional directory: existing active advisor first, then specialty
   match, availability, meeting preference, and capacity. License and state eligibility are never
   inferred; every candidate carries `eligibility_check: "manual_verification_required"`.
6. Model failures preserve the draft. `assign` records the staff member's advisor and reason and
   changes nothing outside this database.

## Language-model adapter interface (Agent 1)

The backend calls two functions with the frozen signatures and supplies authorized tool callbacks.
The adapter never reads files or the database.

```python
intake_turn(client_id: str, transcript: str, selected_option_id: str | None, tools) -> dict
triage_case(confirmed_request: dict, tools) -> dict
```

`tools` is a dict that also supports attribute access (`tools["get_relevant_accounts"]` or
`tools.get_relevant_accounts`). Sync or async functions, a class, or a factory all work; calls run
under a timeout. Shapes:

| Callback | Returns |
| --- | --- |
| `get_relevant_accounts(client_id, phrase)` | `{client_id, accounts: [{account_id, account_type, label, familiar_label, masked_identifier, ownership, former_employer, matched_terms, relevance}], mentioned_account_types, missing_account_types, former_employer_mentioned, error}`. No balances. `error: "not_authorized"` for another client. |
| `get_approved_definition(term)` | `{term, plain, source: "approved_glossary"}` or `None` |
| `get_relevant_account_history(account_id)` | `{account_id, account_type, label, masked_identifier, events: [{type, date, source_id, description}], error}` |
| `search_advisor_directory(categories, preferences)` | `{destination, destination_reason, candidates: [...]}` using the deterministic ranking |
| `get_session_context()` (extra) | prior turns, questions asked, suggestions offered, selections made |
| `list_glossary_terms()` (extra) | `[{key, term}]` |

Expected `intake_turn` output: `{suggestions: [{id, label, account_id?}] (<=3), question, definitions:
[{term, plain}], candidate_intent, selected_account_id (treated as a proposal), uncertainty,
proposed_plain_language_request}`. Expected `triage_case` output: `{client_summary, staff_summary,
intent, categories (fixed taxonomy), unresolved_questions, flags, urgency: {level, reason},
recommended_destination, recommended_advisor_ids}`. The backend validates everything: unknown
categories, unauthorized account ids, definitions not in the glossary, and any account facts are
dropped and noted. Do not use the reserved suggestion ids `none_of_these` or `talk_to_person`.

`confirmed_request` passed to `triage_case` contains `case_id, client_id, client_display_name,
original_words, confirmed_plain_language_request, input_mode, selected_account (public fields, no
balance) | null, account_match_status, amount_requested, currency, candidate_intent,
conversation_notes, client_requested_person, authorized_account_types, mentioned_account_types,
missing_account_types`.

## Seed data (Agent 4)

The store loads `data/clients.json`, `data/accounts.json`, `data/events.json`, `data/advisors.json`,
and `data/glossary.json` when all five exist and parse; otherwise it uses the fallback fixtures in
`backend/fixtures/` and says so in `/health`. Files may be JSON lists or objects wrapping a list.
Canonical fields (common alternatives such as `id`, `name`, `type`, `last4`, `as_of`, `specialty_tags`,
`meeting_mode`, `definition` are also accepted):

- clients: `client_id, display_name, preferred_contact_channel, existing_advisor_id, state, demo_scenario`
- accounts: `account_id, client_id, account_type, label, familiar_label, masked_identifier, ownership, former_employer, balance, balance_as_of, source_id, status`
- events: `event_id, account_id, type, date, source_id, description`
- advisors: `advisor_id, display_name, specialties, region, meeting_modes, capacity, available, active, next_available, existing_client_ids, kind` (`kind: "specialist_queue"` for the security desk)
- glossary: `key, term, aliases, plain`

Account types the deterministic rules understand: `rollover_ira, roth_ira, traditional_ira, brokerage,
joint_brokerage, trust` (others load fine but get no term-mismatch detection).

## Layout

```
backend/
  main.py          app factory, error envelope, static pages, CLI entry
  api.py           the seven contract routes + health/demo helpers
  schemas.py       pydantic models, taxonomy, statuses, destinations
  store.py         SQLite repository + tolerant seed loader
  settings.py      environment configuration
  reset.py         demo reset CLI
  fixtures/        fallback synthetic data (superseded by data/)
  services/
    intake.py      session state machine (start / turn / confirm)
    triage.py      case builder: facts from records, flags, routing
    staff.py       queue, case document, candidates, assignment
    routing.py     deterministic destination + advisor ranking
    tools.py       authorized tool callbacks for the model
    validation.py  sanitizes adapter output
    mock_agent.py  offline adapter with the same signatures as Agent 1's
    agent_adapter.py  loads mock or bedrock, timeout, sync/async
    auth.py        demo role switcher (simulated access control)
    text_rules.py  security keywords, account-term mentions, amounts
  aws/             Agent 1 (Bedrock adapter, config, Transcribe)
frontend/client/   Agent 3    frontend/staff/   Agent 4    data/   Agent 4
tests/backend/     contract, scenario, rule, and store tests
scripts/generate_api_examples.py
```

## What is live and what is simulated

- Live when `SAMEPAGE_AGENT_MODE=bedrock`: language interpretation, clarifying questions, triage
  summaries and categories (Amazon Bedrock via Agent 1's adapter).
- Always deterministic application code: authorization scope, account facts and sources, contradiction
  flags, security routing, advisor ranking, state transitions, assignment.
- Simulated: the demo role switcher, all clients, accounts, balances, events, and advisors.
