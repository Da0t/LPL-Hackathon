# SamePage

**SamePage turns everyday language into a confirmed, correctly routed wealth-management request.**
A client can say *"I need six thousand dollars from the Roth thing from my old job"* and SamePage
notices there is no Roth account, surfaces the real rollover IRA, explains the term in plain words,
confirms what the client meant, and hands an advisor a structured request they can trust, instead of
guessing.

Built for the **2026 LPL Financial University Hackathon** by four parallel AI agents against a frozen
version-one API contract. Awards targeted: *Startup We'd Buy Tomorrow* and *Biggest Business Impact*,
plus the automatic *Best Use of AWS*.

> All data is synthetic. The demo role switcher is **simulated** access control, not production
> authentication. No real LPL system, transaction, appointment, or message ever occurs.

---

## The demo in 60 seconds

1. **Client intake** (`/client`): a client speaks or types a loose request. The agent proposes at
   most three plain-language interpretations grounded in the client's real accounts, explains terms
   from an approved glossary, and asks one question at a time, never inventing an account or amount.
2. **Financial-term normalization:** shorthand, acronyms, and phonetic fragments resolve to the
   right approved term, "R O I" -> *return on investment*, "the tax form" -> *1099-R*, "RMD",
   "401k", then the client confirms.
3. **Client confirms** -> a structured **case** is created (original words, confirmed wording,
   account snapshot with source ids, category tags, unresolved questions).
4. **Staff triage** (`/staff`): the advisor queue updates. Staff open the case, see the two-page
   record and ranked advisor candidates with reasons, and assign one. A possible-fraud case routes to
   **security specialist review**, never to a general advisor.

The **"Advisor dashboard ->"** button on the client header jumps straight to the staff view for the
demo.

---

## Architecture

```
          Client (older investor, plain language)          Staff / advisor
                        │                                        │
                 /client page (Agent 3)                   /staff page (Agent 4)
                        │   browser speech + text               │
                        └───────────────┬───────────────────────┘
                                        │  frozen v1 HTTP contract
                             FastAPI backend (Agent 2)
                     intake state machine · triage · routing
                     authorized tool callbacks · SQLite cases
                                        │
                     ┌──────────────────┴───────────────────┐
             Agent 1 AWS adapter                      Synthetic data (Agent 4)
        Amazon Bedrock (Converse + tools)         clients · accounts · events
        intake_turn() / triage_case()             advisors · glossary · cases
        + Transcribe custom vocabulary            (data/ or backend/fixtures/)
```

The language model only ever **interprets and classifies**. Every fact, authorization check,
account snapshot, security route, and advisor ranking is produced by deterministic application code,
so a confident but wrong model answer can never become a false account fact.

### The four agents (how the work was split)

| Agent | Owns | Key paths |
| --- | --- | --- |
| **Agent 1 , AWS** | Amazon Bedrock intake/triage adapter, model config, pacing/retry, Guardrails hook, Transcribe voice | `backend/aws/`, `infra/`, `AWS_SETUP.md` |
| **Agent 2 , Backend** | FastAPI app, the frozen v1 contract, SQLite storage, authorized tools, routing, validation | `backend/`, `tests/backend/` |
| **Agent 3 , Client UI** | The client intake page: text + browser speech, suggestions, clarification, review/confirm | `frontend/client/`, `tests/client/` |
| **Agent 4 , Staff + Data** | The staff dashboard, synthetic data, the shared data store, demo script | `frontend/staff/`, `data/`, `DEMO_SCRIPT.md` |

Each agent worked on its own branch against `contracts/API_V1.md`; all five pull requests are merged
to `main`.

---

## How we use AWS

SamePage is deliberately a **small agent that works and can be explained** rather than a pile of
services. Every AWS choice earns its place.

### Amazon Bedrock , the language brain (required, live)
- **Converse API with native tool use.** The intake and triage agents call narrow, **client-scoped**
  tools (list the client's real accounts, look up an approved definition, suggest approved terms,
  read account history, search the advisor directory) and return their answer by calling a
  schema-constrained `submit_*` tool, so parsing is deterministic and the model cannot emit an
  invalid shape. Works uniformly across the allowlist (Claude, Nova, Llama).
- **Right-sized model.** `us.anthropic.claude-haiku-4-5-20251001-v1:0` (Claude Haiku 4.5) , fast,
  cheap, strong at tool use, verified enabled in the event account and passing the live smoke test.
  Swappable via `BEDROCK_MODEL_ID` with no code change.
- **Safety by construction.** The adapter injects the authorized client/account id itself (never the
  model's), drops any suggested account the client does not own, discards any model-asserted balance
  or history, and forces `fraud_or_security` cases to specialist review. An optional **Bedrock
  Guardrail** blocks investment/tax advice and masks PII (`infra/guardrail.json`).
- **Reliability.** Calls are paced to roughly one per second and retried with bounded exponential
  backoff on throttling; a hard failure raises a typed error that preserves the client's draft and
  offers a person, rather than crashing the demo.

### Financial-term normalization (grounded in the approved glossary)
Spoken/typed shorthand maps to approved terms before anything is shown. "R O I" -> *return on
investment*, "the tax form" -> *1099-R*, "RMD", "401k", "the Roth thing". The candidates come only
from the glossary (`Store.suggest_terms`), so the agent can suggest and confirm, never invent.

### Amazon Transcribe , voice (custom vocabulary live)
A **custom vocabulary** of financial terms (`samepage-financial-terms`, created and `READY` in the
account) biases speech-to-text toward the right words. `backend/aws/transcribe.py` uses it for live
streaming and file transcription. The client page ships browser speech as the default (labeled as a
browser feature); Transcribe is the AWS-native upgrade. No S3 is required for the core flow.

### Secure and cost-aware by default
- **No credentials in code.** Region and model come from the environment; boto3 uses the event
  account's credential chain. Nothing secret is committed (`.gitignore` blocks `.env`, `.aws/`,
  `*.pem`, local databases).
- **Least privilege.** `infra/iam_policy.json` grants only `bedrock:InvokeModel` on the single model
  (plus optional `ApplyGuardrail` / `StartStreamTranscription`), no wildcards.
- **`us-east-1`**, synthetic data only, S3 avoided in the core (and private if ever added).

Full setup, the model-verification helper, and the live smoke test are in **[`AWS_SETUP.md`](AWS_SETUP.md)**.

---

## Repository structure

```
LPL-Hackathon/
├── backend/                     Agent 2 , FastAPI application
│   ├── main.py                  app factory + `app` entrypoint, error envelope, static pages, CLI
│   ├── api.py                   the seven contract routes + /health, /demo helpers
│   ├── schemas.py               pydantic models, taxonomy, statuses, destinations
│   ├── store.py                 SQLite repository + tolerant seed loader
│   ├── settings.py              environment configuration
│   ├── reset_demo.py            demo reset CLI (reset.py is an alias)
│   ├── fixtures/                fallback copy of Agent 4's data (clients, accounts, …, glossary)
│   ├── services/
│   │   ├── intake.py            session state machine (start / turn / confirm)
│   │   ├── triage.py            case builder: record-backed facts, flags, routing
│   │   ├── case_facts.py        account context, relevant events, sourced conflicts
│   │   ├── staff.py             queue, case document, candidates, assignment
│   │   ├── routing.py           deterministic destination + advisor ranking
│   │   ├── tools.py             authorized tool callbacks (incl. suggest_terms)
│   │   ├── validation.py        sanitizes adapter output
│   │   ├── mock_agent.py        offline adapter with Agent 1's signatures
│   │   ├── agent_adapter.py     loads mock / stub / bedrock, timeout, sync-or-async
│   │   ├── auth.py              demo role switcher (simulated access control)
│   │   └── text_rules.py        security keywords, account-term mentions, amounts
│   └── aws/                     Agent 1 , AWS integration
│       ├── bedrock_agent.py     Bedrock Converse tool-use loop: intake_turn / triage_case
│       ├── config.py            region/model/guardrail/pacing from env (no creds in code)
│       └── transcribe.py        Transcribe streaming + financial custom vocabulary
├── frontend/
│   ├── client/                  Agent 3 , client intake page (served at /client)
│   └── staff/                   Agent 4 , staff dashboard (served at /staff) + dev_server.py
├── data/                        Agent 4 , synthetic seed data + shared store
│   ├── clients.json accounts.json events.json advisors.json glossary.json cases.json
│   ├── store.py                 read-only data layer + the four tool callbacks + suggest_terms
│   └── CONTRACT_V2_PROPOSAL.md  optional additive fields the staff page already reads
├── contracts/
│   ├── API_V1.md                the frozen version-one HTTP contract
│   ├── demo_fixture_v1.json     fixed integration fixture (CLIENT-017, ACCT-201, ADV-03, CASE-1042)
│   └── mock_api.py              standalone mock (port 8001) for isolated UI work
├── infra/
│   ├── iam_policy.json          least-privilege IAM for the adapter
│   └── guardrail.json           optional Bedrock Guardrail definition
├── tests/
│   ├── aws/                     Agent 1 adapter: tool loop, no invented accounts, Transcribe vocab
│   ├── data/                    term-normalization matching
│   ├── backend/                 contract, scenarios, rules, store, app
│   └── client/                  client-page JS tests (Node) + demo screenshots
├── docs/API_EXAMPLES.md         request/response examples from a real run
├── scripts/generate_api_examples.py
├── AWS_SETUP.md                 Agent 1: AWS setup, model verification, smoke test, the seam
├── INTEGRATION_RUNBOOK.md       launch + acceptance steps
├── HACKATHON_PROJECT_BRIEF.md   rules, constraints, judging, schedule
├── SAMEPAGE_PRODUCT_SPEC.md     the product, journeys, data contracts
├── DEMO_SCRIPT.md               the presentation walk-through
├── requirements.txt             app + tests + Agent 1 pins (one install covers everything)
└── requirements-aws.txt         Agent 1 AWS dependencies (mirrored into requirements.txt)
```

---

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt            # FastAPI, Uvicorn, pydantic, boto3, amazon-transcribe, tests
```

### Live Amazon Bedrock (the judged path)

```bash
export AWS_REGION=us-east-1
export BEDROCK_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0   # verify in the event account
export SAMEPAGE_AI_MODE=bedrock
# credentials: event-account profile (e.g. AWS_PROFILE=lpl-hackathon) or standard boto3 chain
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open **<http://127.0.0.1:8000/client>** and **<http://127.0.0.1:8000/staff>**. `/health` reports
`live_model: true` when Bedrock is active. `SAMEPAGE_AI_MODE=bedrock` imports Agent 1's adapter and
**fails fast** if it cannot, so the judged demo never silently falls back to a mock.

| `SAMEPAGE_AI_MODE` | Adapter | Use |
| --- | --- | --- |
| `bedrock` | Agent 1, live Bedrock | the judged demo |
| `stub` | Agent 1's module, offline stub | checking the seam without AWS |
| `mock` (default) | Agent 2's deterministic mock | UI work and the test suite |

### Integrated preview server (alternative, stdlib only)

Agent 4's `frontend/staff/dev_server.py` serves both pages and the whole v1 API on one origin and can
route intake/triage through the live adapter, handy when you want a single file with no FastAPI:

```bash
AWS_REGION=us-east-1 BEDROCK_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0 \
SAMEPAGE_AI_MODE=bedrock python3 frontend/staff/dev_server.py --ai adapter --v2 --port 8001
```

### Demo reset and the Transcribe vocabulary

```bash
python -m backend.reset_demo                 # clears live cases/sessions, reloads seed data
python -m backend.aws.transcribe             # create/refresh the financial custom vocabulary
```

### Tests

```bash
python -m pytest        # 87 Python tests (adapter, term matching, backend contract/rules/store/app)
cd tests/client && npm test   # client-page JS tests (Node)
```

---

## HTTP contract (version one, frozen)

Paths and field names are fixed in [`contracts/API_V1.md`](contracts/API_V1.md); fields beyond it are
additive.

| Endpoint | Role | Request | Response |
| --- | --- | --- | --- |
| `POST /intake/start` | client | `{client_id}` | `{session_id, client_display_name, status}` |
| `POST /intake/{session_id}/turn` | client | `{text, input_mode, selected_option_id?}` | `{suggestions(≤3), question, definitions, candidate_intent, selected_account_id, uncertainty, status, …}` |
| `POST /intake/{session_id}/confirm` | client | `{confirmed_plain_language_request, selected_account_id?, amount_requested?}` | `{case_id, status, client_summary}` |
| `GET /staff/cases` | staff | `?status= ?category=` | `{cases: [...]}` |
| `GET /staff/cases/{case_id}` | staff | | full case record |
| `GET /staff/cases/{case_id}/candidates` | staff | | `{candidates: [...]}` |
| `POST /staff/cases/{case_id}/assign` | staff | `{advisor_id, staff_reason}` | `{case_id, status, assigned_advisor_id}` |

Role is simulated via `X-Demo-Role` (+ `X-Demo-Client-Id` for client calls). Errors are
`{error_code, message}`. Deeper semantics (statuses, flags, the case record, the deterministic rules,
and the Agent 1 tool seam) are documented inline in the code and in `AWS_SETUP.md` §8.

---

## What is live and what is simulated

- **Live (with `SAMEPAGE_AI_MODE=bedrock`):** language interpretation, clarifying questions, term
  normalization, triage summaries and categories , Amazon Bedrock via Agent 1's adapter.
- **Always deterministic application code:** authorization scope, account facts and sources,
  contradiction statements, security routing, advisor ranking, state transitions, assignment.
- **Simulated:** the demo role switcher, and every client, account, balance, event, and advisor.

## Documentation

- [`AWS_SETUP.md`](AWS_SETUP.md) , AWS setup, model verification, live smoke test, the Agent 1 seam
- [`INTEGRATION_RUNBOOK.md`](INTEGRATION_RUNBOOK.md) , launch + acceptance checklist
- [`SAMEPAGE_PRODUCT_SPEC.md`](SAMEPAGE_PRODUCT_SPEC.md) , product, journeys, data contracts
- [`HACKATHON_PROJECT_BRIEF.md`](HACKATHON_PROJECT_BRIEF.md) , rules, constraints, judging
- [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md) , the 5-minute presentation walk-through
- [`contracts/API_V1.md`](contracts/API_V1.md) , the frozen HTTP contract
