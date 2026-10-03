# Coherent / SamePage

**SamePage turns everyday language into a confirmed, correctly routed wealth-management request.**
A client can say *"I need six thousand dollars from the Roth thing from my old job"* and SamePage
notices there is no Roth account, surfaces the real rollover IRA, explains the term in plain words,
confirms what the client meant, and hands an advisor a structured request they can trust, instead of
guessing.

Built for the **2026 LPL Financial University Hackathon** by four parallel AI agents against a frozen
version-one API contract. Awards targeted: *Startup We'd Buy Tomorrow* and *Biggest Business Impact*,
plus the automatic *Best Use of AWS*.

> Start the current application at **http://127.0.0.1:3200/login**. The client portal uses real
> Amazon Cognito authentication and DynamoDB storage; all people and financial records remain
> fictional. See [Client portal setup](#client-portal-upgrade-october-3) below. Legacy `/client`
> and `/staff` pages describe the earlier prototype. No transaction or appointment is executed.
>
> **Maintenance rule:** update this README whenever a significant feature, workflow, infrastructure,
> configuration, or validation procedure changes.

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
python -m pytest        # 96 Python tests, including portal authorization, persistence and financial data invariants
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

With `COHERENT_PORTAL_CONFIG`, roles come from validated Cognito sessions and server-owned identity mappings. Without that setting, legacy tests simulate roles via `X-Demo-Role` (+ `X-Demo-Client-Id`). Errors are
`{error_code, message}`. Deeper semantics (statuses, flags, the case record, the deterministic rules,
and the Agent 1 tool seam) are documented inline in the code and in `AWS_SETUP.md` §8.

---

## What is live and what is simulated

- **Live (with `SAMEPAGE_AI_MODE=bedrock`):** language interpretation, clarifying questions, term
  normalization, triage summaries and categories , Amazon Bedrock via Agent 1's adapter.
- **Always deterministic application code:** authorization scope, account facts and sources,
  contradiction statements, security routing, advisor ranking, state transitions, assignment.
- **Synthetic:** every client, account, balance, event, and advisor. Only the legacy unconfigured backend accepts the simulated demo role switcher.

## Documentation

- [`AWS_SETUP.md`](AWS_SETUP.md) , AWS setup, model verification, live smoke test, the Agent 1 seam
- [`INTEGRATION_RUNBOOK.md`](INTEGRATION_RUNBOOK.md) , launch + acceptance checklist
- [`SAMEPAGE_PRODUCT_SPEC.md`](SAMEPAGE_PRODUCT_SPEC.md) , product, journeys, data contracts
- [`HACKATHON_PROJECT_BRIEF.md`](HACKATHON_PROJECT_BRIEF.md) , rules, constraints, judging
- [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md) , the 5-minute presentation walk-through
- [`contracts/API_V1.md`](contracts/API_V1.md) , the frozen HTTP contract

## Client portal upgrade (October 3)

The new `/workspace` experience replaces the fictional-client selector with a normal Cognito email/password sign-in. Client profiles, accounts, history, and immutable submitted request documents use a private, on-demand DynamoDB table in `us-east-1`. Identity-to-client and staff-role mappings are server-owned; changing demo headers cannot impersonate another client when the portal is enabled. Passwords are managed by Cognito, session tokens use HttpOnly SameSite cookies, and the Next.js `/api` proxy keeps browser requests on one origin. The original SQLite intake/case engine remains in use locally; its account lookup is synchronized from the cloud records.

Three fictional households have detailed personal/contact/employment information, financial preferences, retirement and brokerage accounts, cash and education savings, holdings, beneficiaries, and dated history. SSNs are represented by **last four digits only**. These records must stay synthetic. User-entered account facts and historical activity are explicitly marked as self-reported; entering a transfer history record never moves money or changes a balance.

Field research: [Schwab brokerage account information](https://www.schwab.com/brokerage), [Fidelity transaction-history categories](https://www.fidelity.com/webcontent/ap002390-mlo-content/18.04/help/learn_history.shtml), and [Fidelity cost-basis explanations](https://www.fidelity.com/webxpress/help/topics/learn_account_cost_basis.shtml) informed the profile fields, holdings, contributions, transfers, trades, dividends, reinvestment, fees, and retirement activity. These sources inform the data model, not personalized financial advice.

Provision resources with `AWS_DEFAULT_REGION=us-east-1 .venv/bin/python -m scripts.provision_portal` using the standard AWS credential chain. The script sends **no invitation emails or SMS**. It saves resource configuration to ignored `var/portal-aws.json` and generated demo sign-ins to private, ignored `var/demo-access.json`. It preserves existing profiles on rerun. Never commit either sign-ins or AWS credentials. DynamoDB uses encryption at rest; [Cognito authentication](https://docs.aws.amazon.com/cognito-user-identity-pools/latest/APIReference/API_InitiateAuth.html) and [GetUser validation](https://docs.aws.amazon.com/cognito-user-identity-pools/latest/APIReference/API_GetUser.html) provide the identity boundary.

Run the authenticated backend with `COHERENT_PORTAL_CONFIG=var/portal-aws.json SAMEPAGE_AI_MODE=bedrock .venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`. Supply a verified Bedrock model and AWS credentials as described in `AWS_SETUP.md`; `SAMEPAGE_AI_MODE=mock` is the explicit offline AI option. Without `COHERENT_PORTAL_CONFIG`, the old simulated API mode remains available for legacy tests only. Run the frontend with `cd web && npm run dev -- --hostname 127.0.0.1 --port 3200`.

### Client screens and request documents

- `/login`: email/password sign-in, with no fictional-client picker.
- `/workspace`: per-client overview, asset/cash snapshots, accounts, and recent activity.
- `/workspace/profile`: editable identity, contact/address, employment, household finances, goals, and trusted contact fields. Contact email and Cognito sign-in email are intentionally separate.
- `/workspace/finances`: account list, holdings, editable account details, searchable/type-filtered history, account creation, and past-activity entry. Account types include brokerage/joint, traditional/Roth/rollover/SEP/SIMPLE IRAs, 401(k), 403(b), 457(b), HSA, 529, trusts, cash, savings, and CDs.
- `/workspace/requests/new`: three generous columns for the client's words, clarification/review, and an A4-proportioned document. The document includes the client's name, description, original words, chosen account's exact dated balances and holdings, and account-specific history with source IDs. Print / Save PDF uses A4 print CSS and flows long histories across pages. No SSN is included in the request document.
- `/workspace/requests`: immutable submitted document snapshots stored in DynamoDB. A failed cloud archive can be retried without submitting another request.

Seed histories include reconciled account-value ledgers and matched transfer legs; holdings plus cash match the recorded balances. These are fictional statements, not market feeds. Editing an account replaces its holdings presentation with a self-reported balance awaiting verification so old positions are not presented as a reconciliation of the new value. New historical notes do not recalculate balances.

### Validation and operational boundaries

The seeded portal contains **3 clients, 16 accounts, and 154 activity records**. The 96-test Python suite covers existing intake/routing plus client isolation, impersonation attempts, profile edit conflicts, historical transfer validation, ledger reconciliation, and immutable request snapshots. `cd web && npx tsc --noEmit` checks the frontend; build-time type checking is enabled. React 19/Motion typing in the existing shared animation components was corrected as part of enabling this check.

For a live browser integration check, install Playwright in a local test environment, start the two servers, then run `NODE_PATH=/path/to/playwright/node_modules node tests/portal/browser.cjs` from the repository root. It reads `var/demo-access.json` (override with `PORTAL_ACCESS_FILE`), signs in all three clients and staff, saves/restores a profile edit, submits one fictional request through Bedrock and DynamoDB, checks the staff queue, and checks mobile layouts and draft restoration. It creates a synthetic case and writes screenshots/print output under `/tmp`; it does not send communications or execute financial transactions.

This is a localhost prototype with real AWS identity/storage, not a production financial system. Cognito sessions expire after one hour and require sign-in again. Self-registration, password reset UI, MFA, bank connectivity, and full SSN collection are not implemented. Intake sessions and the staff case workflow still require the local SQLite database; only client records and archived request documents are cloud-persisted. AWS session credentials must remain valid for backend calls. Before hosting publicly, configure HTTPS with Secure cookies and an explicit allowed origin (`COHERENT_ALLOWED_ORIGINS`); the current proxy targets the backend on localhost. Browser voice uses the browser's speech service and requires permission. Typed requests remain fully usable when voice is unavailable.

Live acceptance completed: all three Cognito client logins and the staff login, a Bedrock-assisted confirmed request, its DynamoDB document archive and staff visibility, profile persistence, logout, client isolation, draft restoration without automatic submission, and all four client screens at a 390px viewport. Printed request output was inspected as A4 pages with complete account values and history.

Production validation: `npm run build` passes with TypeScript checking enabled; all 96 Python tests and 7 legacy client browser tests pass. The client portal's live browser smoke also passes. The current local preview uses the production build (`cd web && npm run start -- --hostname 127.0.0.1 --port 3200`). Use the development command above when editing. The SQLite reference history is replaced from each client's cloud record so legacy seed events cannot contradict the portal's history.
