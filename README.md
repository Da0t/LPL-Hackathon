# Coherent

**Coherent turns everyday language into a confirmed, correctly routed wealth-management request, and
hands the advisor a case they can act on.** A client can say *"I need six thousand dollars from the
Roth thing from my old job"*; Coherent notices there is no Roth account, surfaces the real rollover
IRA, confirms what the client meant, and routes a structured request to the right advisor, who opens
it to a prepared action packet instead of a cold transcript.

Built for the **2026 LPL Financial University Hackathon**. Awards targeted: *Startup We'd Buy
Tomorrow* and *Biggest Business Impact*, plus the automatic *Best Use of AWS*.

> All people and financial records are fictional. No real financial transaction, appointment, email,
> or SMS is ever sent.
>
> The product is **Coherent**. Some internal identifiers kept from the original codebase still read
> `samepage` (for example the `SAMEPAGE_AI_MODE` environment variable); those are technical names,
> not the product.

**Documentation maintenance:** update this README whenever a significant feature, workflow,
infrastructure, configuration, or validation procedure changes. Describe the behavior available on
the current branch and clearly identify work that is still awaiting integration.

---

## The demo in 60 seconds

1. **Client portal** (`/login`, then `/workspace`). A signed-in client speaks or types a loose
   request in the request editor. Amazon Bedrock proposes up to three plain-language interpretations
   grounded in the client's real accounts, normalizes shorthand to approved terms ("R O I" becomes
   *return on investment*, "the tax form" becomes *1099-R*), and asks one question at a time. It
   never invents an account or an amount.
2. **Client confirms.** A structured **case** is created: original words, confirmed wording, account
   snapshot with source ids, category tags, and unresolved questions. Possible fraud routes to a
   security specialist queue, never to a general advisor.
3. **Advisor workspace** (`/dashboard`). The queue ranks itself and says why in plain words
   ("Waiting 2 days for an advisor"). The advisor opens the case to a **prepared action packet**:
   proposed fields, compliance checks, and a draft message, ready to approve.
4. **Advisor agents.** A **reply drafter** and a **compliance reviewer** work in a loop (draft,
   review, one revision, review), next to a **prep brief**, a **next-steps planner** with an owner
   for each step, and a **security investigator** for fraud cases.
5. **Follow-up.** The advisor's message appears in the client's own workspace. The client replies
   there, and the case returns to the top of the advisor's queue.
6. **Impact** (`/dashboard`, Impact in the sidebar). Turns and seconds to a confirmed request,
   measured from requests submitted in the workspace, next to an advisor capacity model whose inputs
   are editable assumptions.

The speaking and clicking plan is in [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md).

---

## Architecture

```
        Client (plain language)                          Advisor
              │                                             │
     web/ /login, /workspace (Next.js)            web/ /dashboard (Next.js)
     request editor + request document            queue, action packet, agents
              └───────────────┬─────────────────────────────┘
                              │  same-origin /api proxy, HttpOnly session cookie
                   backend/ , FastAPI
        intake · triage · routing · staff workflow · client follow-up
              │                    │                       │
   backend/aws               backend/portal          backend/store.py
   Amazon Bedrock            Amazon Cognito          SQLite: intake sessions,
   intake, triage,           (sign-in) and           cases, assignments
   action packet, brief,     DynamoDB (client        (local; reference records
   four advisor agents       records, archived       synchronized from the
   (+ Guardrails hook)       request documents)      cloud profiles)
```

The language model only **interprets, classifies, and drafts**. Every fact, authorization check,
account snapshot, security route, advisor ranking, and compliance verdict is deterministic
application code, so a confident but wrong model answer can never become a false account fact.

---

## How we use AWS

- **Amazon Bedrock (Converse API with native tool use).** Intake and triage interpret the client's
  words and classify the request through narrow, client-scoped tools with schema-forced output. On
  the advisor side, Bedrock prepares the action packet and the prep brief and runs four **advisor
  agents** (reply drafter, compliance reviewer, next-steps planner, security investigator). Each
  agent is a single Bedrock call that must answer through one tool with a fixed schema, and each has
  a deterministic offline fallback. There is no orchestration framework: the only loop is draft,
  review, one revision, review, run by plain code in `backend/services/reply_workflow.py`. The model
  is **Claude Haiku 4.5** (`us.anthropic.claude-haiku-4-5-20251001-v1:0`), swappable via
  `BEDROCK_MODEL_ID`.
- **Amazon Cognito and DynamoDB.** Cognito handles email and password sign-in for clients and staff.
  A private, on-demand DynamoDB table holds client profiles, accounts, history, and immutable
  snapshots of submitted request documents. Identity-to-client and staff-role mappings are owned by
  the server, so changing a request header cannot impersonate another client.
- **Safety by construction.** The adapter injects authorized ids (never the model's), drops invented
  accounts, forces fraud cases to specialist review, and never asserts balances or history. The
  compliance verdict is computed in code from what the reviewer quoted, never taken from the model.
  Optional **Bedrock Guardrails** block investment and tax advice.
- **Amazon Transcribe.** A financial custom vocabulary (`samepage-financial-terms`) is created and
  the streaming adapter is built in `backend/aws/transcribe.py`, but no page calls it yet. Voice
  input in the demo uses the browser's speech service.
- **Reliability and security.** About one Bedrock call a second with bounded retry and graceful
  failure; least-privilege IAM (`infra/iam_policy.json`); `us-east-1`; DynamoDB encryption at rest;
  synthetic data; no credentials in code.

Bedrock setup, model verification, and the live smoke test: [`AWS_SETUP.md`](AWS_SETUP.md).

---

## Run it

**1. Install and provision** (repo root, once):

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
AWS_DEFAULT_REGION=us-east-1 python -m scripts.provision_portal
```

The provisioning script uses the standard AWS credential chain and sends **no invitation emails or
SMS**. It saves resource configuration to `var/portal-aws.json` and generated demo sign-ins to
`var/demo-access.json`. Both files are ignored by git; never commit sign-ins or AWS credentials. It
preserves existing profiles on rerun.

**2. Backend** (repo root), with live Bedrock and the authenticated portal:

```bash
AWS_PROFILE=lpl-hackathon AWS_REGION=us-east-1 \
  BEDROCK_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0 \
  COHERENT_PORTAL_CONFIG=var/portal-aws.json SAMEPAGE_AI_MODE=bedrock \
  python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

`SAMEPAGE_AI_MODE=mock` replaces AI calls with deterministic responses. The authenticated portal
still requires AWS credentials for Cognito and DynamoDB.

**3. Frontend:**

```bash
cd web
pnpm install
PORT=3200 pnpm dev          # use 3200, not 3000 (a stale service worker hijacks 3000)
```

Open **http://127.0.0.1:3200/login** and use a client or staff sign-in from `var/demo-access.json`.
`/workspace` is the client portal and `/dashboard` is the advisor workspace. Sign-in is a cookie, so
use two browser windows (one private) to show a client and an advisor side by side.

**Reset between runs:** `python -m backend.reset_demo` clears intake sessions, live cases, and
assignments and reloads the seed data. The server does not need to restart.

### Local click-through sign-in (no AWS, no passwords)

For development, start the backend with `COHERENT_DEV_LOGIN=1` and without
`COHERENT_PORTAL_CONFIG`:

```bash
COHERENT_DEV_LOGIN=1 SAMEPAGE_AI_MODE=mock \
  python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

`/login` then shows one button per seeded user (staff and the three clients). Portal records are
the synthetic seed profiles held in memory and reset on restart. `COHERENT_PORTAL_CONFIG` takes
precedence, so this mode is never active alongside Cognito. Localhost only; never enable it on a
reachable server.

With neither variable set, the API runs in a legacy mode that simulates roles with request headers.
That mode exists for the offline test suite and the legacy pages only.

### Tests

```bash
python -m pytest                    # backend, AWS adapter, portal, term matching
cd web && npx tsc --noEmit          # frontend types
cd web && npm run build             # production build, type checking enabled
```

The follow-up workflows have regression coverage in `tests/backend/test_advisor_workspace.py`,
`test_reply_workflow.py`, and `test_workspace_followups.py`. Advisor agent output validation is in
`tests/aws/test_advisor_agents.py`, and client isolation, impersonation attempts, profile edit
conflicts, ledger reconciliation, and immutable request snapshots are in `tests/portal/`.

For a live browser check, install Playwright in a local test environment, start both servers, then
run `NODE_PATH=/path/to/playwright/node_modules node tests/portal/browser.cjs` from the repository
root. It reads `var/demo-access.json` (override with `PORTAL_ACCESS_FILE`), signs in all three
clients and staff, saves and restores a profile edit, submits one fictional request through Bedrock
and DynamoDB, checks the staff queue, and checks mobile layouts and draft restoration. It creates a
synthetic case and writes screenshots under `/tmp`.

---

## Screens

### Client

- `/login`: email and password sign-in.
- `/workspace`: overview with asset and cash snapshots, accounts, and recent activity.
- `/workspace/profile`: editable identity, contact, employment, household finances, goals, and
  trusted contact. Contact email and sign-in email are intentionally separate.
- `/workspace/finances`: accounts, holdings, editable account details, searchable history, account
  creation, and past-activity entry. Facts a client enters are marked as self-reported; entering a
  transfer never moves money or changes a balance.
- `/workspace/requests/new`: three columns for the client's words, the clarification, and an
  A4-proportioned request document. The document carries the client's name, the description, the
  original words, the chosen account's dated balances and holdings, and account history with source
  ids. No SSN appears in it. Print or Save PDF uses A4 print CSS. `/intake` redirects here.
- `/workspace/requests`: request status, advisor clarification messages, the client's replies, and
  the immutable document snapshots stored in DynamoDB. A failed cloud archive can be retried without
  submitting another request.

Staff notes, flags, and routing details are never shown in the client view.

### Advisor (`/dashboard`)

- **Queue** with plain-language priority, filters, search, and a **Pipeline** board by workflow
  stage.
- **Case view.** The Overview leads with the prepared action packet; approving it records a workflow
  event and sends the draft message to the client. It does not execute a financial transaction.
  Further tabs hold next steps (or the security review for fraud cases), the client snapshot
  (accounts, recent activity, other requests), advisor assignment, and compliance and history.
- **Messaging.** A message to the client is checked by the compliance reviewer before it is
  recorded; a flagged message needs a revision or an explicit override, which is recorded on the
  case. A client reply returns the case to its assigned advisor, or to staff review if unassigned.
- **Security and reassignment.** Security cases can be escalated to the specialist workflow.
  Reassignment records the prior advisor and the staff reason in case history.
- **Caching.** Prep briefs, next-step plans, and investigations reuse cached results for unchanged
  cases and can be regenerated.
- **Impact** view with measured intake numbers and the editable capacity model.

---

## Repository structure

```
LPL-Hackathon/
├── web/                     the demo frontend (Next.js, Geist, Tailwind)
│   ├── app/                 landing, login/, workspace/ (client portal), dashboard/ (advisor)
│   ├── components/          dashboard/ (case view and agent panels), portal/ (client shell,
│   │                        request document), landing sections, ui/ (shadcn)
│   └── lib/                 api.ts (advisor and intake client), portal.ts (client portal client)
├── backend/                 FastAPI app
│   ├── main.py api.py       app and routes: v1 contract plus advisor endpoints under
│   │                        /staff/cases/{id}/ and client follow-up under /my/requests
│   ├── services/            intake, triage, routing, validation, staff workflow, priority (queue
│   │                        ranking and intake metrics), reply_workflow, client_requests
│   ├── portal/              Cognito sign-in, DynamoDB persistence, seed profiles, dev sign-in
│   ├── aws/                 Bedrock adapter (intake, triage, brief), advisor_agents, transcribe
│   └── store.py             SQLite cases plus reference records synchronized from the portal
├── data/                    synthetic seed data
├── contracts/               frozen v1 HTTP contract, fixture, standalone mock
├── infra/                   least-privilege IAM and Bedrock Guardrail config
├── scripts/                 provision_portal.py, generate_api_examples.py
├── tests/                   aws/, backend/, data/, portal/, client/ (legacy page tests)
└── frontend/                LEGACY pages served by the backend at /client and /staff
                             (pre-Coherent); web/ is the demo
```

---

## What is live and what is simulated

- **Live AWS:** Cognito sign-in, DynamoDB client records and archived request documents, and (with
  `SAMEPAGE_AI_MODE=bedrock`) language interpretation, clarifying questions, term normalization,
  triage, the action packet, the prep brief, and the four advisor agents.
- **Always deterministic:** authorization scope, account facts and sources, security routing, advisor
  ranking, queue priority, the compliance verdict, case state, assignment, and the workflow actions.
- **Synthetic:** every client, account, balance, event, and advisor. Three fictional households have
  detailed profiles, 16 accounts, and 154 activity records; SSNs are represented by their last four
  digits only. Clarification messages and replies stay inside the demo.
- **Measured:** client turns and seconds from first message to confirmation, for requests submitted
  in the workspace. **Not measured:** advisor time saved. The capacity model on the Impact view is a
  formula with assumed inputs.

## Operational boundaries

This is a localhost prototype with real AWS identity and storage, not a production financial system.

- Cognito sessions expire after one hour and require sign-in again.
- Self-registration, password reset, MFA, bank connectivity, and full SSN collection are not
  implemented.
- Intake sessions and the staff case workflow use the local SQLite database; only client records and
  archived request documents are persisted in the cloud.
- AWS session credentials must remain valid for backend calls.
- Before hosting publicly, configure HTTPS with Secure cookies and an explicit allowed origin
  (`COHERENT_ALLOWED_ORIGINS`); the frontend proxy targets the backend on localhost.
- Seed histories include reconciled account-value ledgers and matched transfer legs. They are
  fictional statements, not market feeds. Editing an account replaces its holdings with a
  self-reported balance awaiting verification.

The profile fields, holdings, and activity categories were modeled on public brokerage documentation:
[Schwab brokerage account information](https://www.schwab.com/brokerage),
[Fidelity transaction-history categories](https://www.fidelity.com/webcontent/ap002390-mlo-content/18.04/help/learn_history.shtml),
and [Fidelity cost-basis explanations](https://www.fidelity.com/webxpress/help/topics/learn_account_cost_basis.shtml).
These inform the data model, not personalized financial advice.

## Documentation

- [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md): the five-minute speaking and clicking plan, plus likely questions
- [`web/README.md`](web/README.md): frontend run and structure
- [`AWS_SETUP.md`](AWS_SETUP.md): Bedrock setup, model verification, smoke test
- [`contracts/API_V1.md`](contracts/API_V1.md): frozen v1 HTTP contract (advisor, follow-up, and portal endpoints are additive)
- [`HACKATHON_PROJECT_BRIEF.md`](HACKATHON_PROJECT_BRIEF.md): event rules, constraints, and judging criteria
- [`SAMEPAGE_PRODUCT_SPEC.md`](SAMEPAGE_PRODUCT_SPEC.md): the original specification (historical)
