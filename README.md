# Coherent

**Coherent turns everyday language into a confirmed, correctly routed wealth-management request, and
hands the advisor a ready-to-act brief.** A client can say *"I need six thousand dollars from the Roth
thing from my old job"*; Coherent notices there is no Roth account, surfaces the real rollover IRA,
confirms what the client meant, and routes a structured request to the right advisor, who opens it to
a Bedrock-generated prep brief instead of a cold transcript.

Built for the **2026 LPL Financial University Hackathon**. Awards targeted: *Startup We'd Buy
Tomorrow* and *Biggest Business Impact*, plus the automatic *Best Use of AWS*.

> The client portal uses real Amazon Cognito sign-in and DynamoDB storage when
> `COHERENT_PORTAL_CONFIG` is set. All people and financial records are fictional; no real
> financial transaction, appointment, email, or SMS is sent. Legacy unconfigured API mode uses
> simulated role headers for offline tests.
>
> Note: the product is **Coherent**. Some internal identifiers kept from the original codebase still
> read `samepage` (e.g. the `SAMEPAGE_AI_MODE` env var, `backend/aws`); those are technical names, not
> the product.

**Documentation maintenance:** update this README whenever a significant feature, workflow,
infrastructure, configuration, or validation procedure changes. Describe the behavior available on
the current branch and clearly identify work that is still awaiting integration.

---

## The demo in 60 seconds

1. **Client portal** (`/login` → `/workspace`, with `/intake` redirecting to the request editor) , a client speaks or types a loose request. Amazon Bedrock proposes
   up to three plain-language interpretations grounded in the client's real accounts, normalizes
   shorthand/acronyms to approved terms ("R O I" -> *return on investment*, "the tax form" ->
   *1099-R*), and asks one question at a time, never inventing an account or amount. The three-column editor combines the client’s words, clarification, and an A4 request document.
2. **Client confirms** -> a structured **case** is created (original words, confirmed wording, account
   snapshot with source ids, category tags, unresolved questions). Possible fraud routes to a security
   specialist queue, never a general advisor.
3. **Advisor workspace** (`/dashboard`) , the advisor opens the case to an **AI prep brief** (the ask
   in advisor terms, talking points, facts to confirm, compliance cautions, generated live by
   Bedrock), then acts on it , **Claim / Note / Request clarification / Mark scheduled / Resolve** ,
   and watches it move across the **My pipeline** board, with a **compliance** panel alongside.
4. **Advisor agents** , four more agents work the case: a **reply drafter** and a **compliance
   reviewer** in a loop (draft, review, one revision, review), a **next-steps planner** with an owner
   for each step, and a **security investigator** for fraud cases. The queue ranks itself and says why
   in plain words ("Waiting 2 days for an advisor").
5. **Impact** (`/dashboard`, Impact in the sidebar) , turns and seconds to a confirmed request,
   measured from intakes run in the workspace, next to an advisor capacity model whose inputs are
   editable assumptions.

### Advisor and client follow-up

The advisor case view leads with a prepared action packet containing proposed fields, checks, and
drafts for review. Approval records a workflow event; it does not execute a financial transaction.
The client snapshot brings together the client's accounts, recent activity, and other requests.

Advisors can request clarification from the client inside the demo. The backend checks the message
with the compliance reviewer before recording it; flagged messages require revision or an explicit,
recorded override. Clients see their own requests and clarification messages in the authenticated `/workspace/requests` view, and can reply while a request is waiting on them. A reply returns the case to its
assigned advisor, or to staff review if it has no assignment. Staff notes, flags, and routing details
are excluded from this client view. No email or SMS is sent.

Security cases can be escalated to the specialist workflow. Advisor reassignment records the prior
advisor and staff reason in case history. Prep briefs, next-step plans, and investigations reuse
cached results for unchanged cases and can be explicitly regenerated.

---

## Architecture

```
        Client (plain language)                         Advisor
              │                                            │
       web/ /workspace (Next.js)                     web/ /dashboard (Next.js)
              │        Cognito + A4 requests                  │  AI prep brief + actions
              └───────────────┬────────────────────────────┘
                              │  HTTP (frozen v1 contract + additive advisor endpoints)
                   backend/ , FastAPI
            intake · triage · routing · case store (SQLite)
                              │
              ┌───────────────┴────────────────┐
     backend/aws , Amazon Bedrock         data/ , synthetic records
   Live Bedrock surfaces:                 clients · accounts · events
   (1) intake_turn / triage_case         advisors · glossary · cases
   (2) advisor prep brief
   (3) advisor agents: reply drafter,
       compliance reviewer, next-steps
       planner, security investigator
   (+ Transcribe custom vocabulary, Guardrails hook)
```

The language model only **interprets, classifies, and briefs**. Every fact, authorization check,
account snapshot, security route, and advisor ranking is deterministic application code. Generated
action fields and drafts additionally go through an independent record audit. This reduces unsupported
claims; it is not a guarantee that a model can never make a mistake.

---

## How we use AWS

- **Amazon Cognito and DynamoDB:** authenticated client/staff sessions, private client profiles, financial records, and immutable request document snapshots. The backend resolves record ownership from its identity map.

- **Amazon Bedrock (Converse / ConverseStream + native tool use).** Intake and triage interpret
  client requests, Forge prepares a packet, and a separate Verifier call audits it against the record.
  Briefing, reply drafting, Sentinel compliance review, planning, and investigation use structured tool
  output. Reply drafting has a bounded draft → review → revision → review loop. Staff operations stream
  real content deltas and stage/tool events over authenticated SSE. Model: **Claude Haiku 4.5**
  (`us.anthropic.claude-haiku-4-5-20251001-v1:0`), configurable with `BEDROCK_MODEL_ID`.
- **Bedrock Knowledge Bases + S3 Vectors + Titan Text Embeddings v2:** Sentinel retrieves registered
  SEC and IRS guidance excerpts, with source URLs and quoted evidence. See the corpus limits below.
- **Amazon Polly:** authenticated neural Joanna read-aloud for questions, options, and request messages.
  Browser speech recognition supplies optional voice input; typed input is always available.
- **Safety by construction** , the adapter injects authorized ids (never the model's), drops invented
  accounts, forces fraud cases to specialist review, and never asserts balances/history. The
  compliance verdict is computed in code from what the reviewer quoted, never taken from the model. Optional
  **Bedrock Guardrails** block investment/tax advice.
- **Amazon Transcribe** , a financial **custom vocabulary** (`samepage-financial-terms`, created +
  READY) biases speech-to-text toward financial terms.
- **Reliability + security** , ~1 call/sec pacing, bounded retry, graceful failure; least-privilege
  IAM (`infra/iam_policy.json`); `us-east-1`; synthetic data; no credentials in code.

Full setup, model verification, and the live smoke test: [`AWS_SETUP.md`](AWS_SETUP.md).

---

## Run it

**1. Backend** (repo root) , live Bedrock:

```bash
pip install -r requirements.txt
AWS_PROFILE=lpl-hackathon AWS_REGION=us-east-1 \
  BEDROCK_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0 \
  COHERENT_PORTAL_CONFIG=var/portal-aws.json SAMEPAGE_AI_MODE=bedrock \
  python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

`SAMEPAGE_AI_MODE=mock` replaces AI calls with deterministic responses. The authenticated portal still requires AWS credentials for Cognito and DynamoDB; omit `COHERENT_PORTAL_CONFIG` only for legacy offline API tests. Provision the portal first using the instructions below.

**2. Frontend** (the demo UI):

```bash
cd web
pnpm install
PORT=3200 pnpm dev          # use 3200, not 3000 (a stale service worker hijacks 3000)
```

Open **http://127.0.0.1:3200/login**, then use a client or staff sign-in. `/workspace` is the client portal and `/dashboard` is the advisor workspace. See
[`web/README.md`](web/README.md).

**Tests:** `python -m pytest` (backend + AWS adapter + term matching).

The follow-up workflows have regression coverage in `tests/backend/test_advisor_workspace.py`,
`test_reply_workflow.py`, and `test_workspace_followups.py`; advisor agent output validation is in
`tests/aws/test_advisor_agents.py`.


---

## Repository structure

```
LPL-Hackathon/
├── web/                     THE demo , Coherent frontend (Next.js + Geist + Tailwind)
│   ├── app/                 page.tsx (landing), login/, workspace/, intake/ redirect, dashboard/
│   ├── components/          hero, pipeline-preview, routing-graph, brand-logo, dashboard UI, ui/ (shadcn)
│   ├── lib/api.ts           typed client for the backend
│   └── public/              coherent-logo.png, coherent-icon.png
├── backend/                 FastAPI app
│   ├── main.py api.py       app + routes (v1 contract + additive advisor endpoints: /brief, /action,
│   │                        /plan, /reply-draft, /compliance-review, /next-steps, /investigation, /client;
│   │                        client follow-up: /my/requests and /my/requests/{case_id}/reply)
│   ├── services/            intake, triage, staff (brief + actions), routing, tools, validation,
│   │                        priority (queue ranking + intake metrics), reply_workflow (drafter/reviewer loop),
│   │                        client_requests (client-visible status and clarification replies)
│   ├── store.py             SQLite cases + cloud-synchronized reference records
│   ├── portal/               Cognito authorization, DynamoDB persistence, synthetic client profiles
│   └── aws/                 Amazon Bedrock adapter (intake_turn, triage_case, advisor_brief), advisor_agents, config, transcribe
├── data/                    synthetic seed data + shared store
├── contracts/               frozen v1 HTTP contract, fixture, standalone mock
├── infra/                   least-privilege IAM + Bedrock Guardrail config
├── tests/                   aws/ , data/ , backend/
├── AWS_SETUP.md             AWS setup, model verification, smoke test, the adapter seam
├── INTEGRATION_RUNBOOK.md · SAMEPAGE_PRODUCT_SPEC.md · HACKATHON_PROJECT_BRIEF.md · DEMO_SCRIPT.md
└── frontend/client, frontend/staff   LEGACY FastAPI-served UI (pre-Coherent); web/ is the demo now
```

---

## What is live and what is simulated

- **Live (with `SAMEPAGE_AI_MODE=bedrock`):** language interpretation, clarifying questions, term
  normalization, triage, the advisor prep brief, and the four advisor agents , Amazon Bedrock.
- **Always deterministic:** authorization scope, account facts and sources, security routing, advisor
  ranking, queue priority, the compliance verdict, case state, assignment, and the workflow/lifecycle
  actions.
- **Synthetic:** every client, account, balance, event, and advisor. Role headers only simulate access when the portal is unconfigured.
  Clarification messages and replies are stored and displayed inside the demo; no external email
  or SMS is sent, and no real transaction or appointment is executed.
- **Measured:** client turns and seconds from first message to confirmation, for intakes run in the
  workspace. **Not measured:** advisor time saved. The capacity model on the Impact view is a formula
  with assumed inputs.

## Documentation

- [`web/README.md`](web/README.md) , frontend run + structure
- [`AWS_SETUP.md`](AWS_SETUP.md) , AWS setup, model verification, smoke test
- [`contracts/API_V1.md`](contracts/API_V1.md) , frozen HTTP contract (all advisor endpoints are additive)
- [`SAMEPAGE_PRODUCT_SPEC.md`](SAMEPAGE_PRODUCT_SPEC.md) · [`HACKATHON_PROJECT_BRIEF.md`](HACKATHON_PROJECT_BRIEF.md) · [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md)


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

The seeded portal contains **3 clients, 16 accounts, and 154 activity records**. The Python suite covers existing intake/routing plus client isolation, impersonation attempts, profile edit conflicts, historical transfer validation, ledger reconciliation, and immutable request snapshots. `cd web && npx tsc --noEmit` checks the frontend; build-time type checking is enabled. React 19/Motion typing in the existing shared animation components was corrected as part of enabling this check.

For a live browser integration check, install Playwright in a local test environment, start the two servers, then run `NODE_PATH=/path/to/playwright/node_modules node tests/portal/browser.cjs` from the repository root. It reads `var/demo-access.json` (override with `PORTAL_ACCESS_FILE`), signs in all three clients and staff, saves/restores a profile edit, submits one fictional request through Bedrock and DynamoDB, checks the staff queue, and checks mobile layouts and draft restoration. It creates a synthetic case and writes screenshots/print output under `/tmp`; it does not send communications or execute financial transactions.

This is a localhost prototype with real AWS identity/storage, not a production financial system. Cognito sessions expire after one hour and require sign-in again. Self-registration, password reset UI, MFA, bank connectivity, and full SSN collection are not implemented. Intake sessions and the staff case workflow still require the local SQLite database; only client records and archived request documents are cloud-persisted. AWS session credentials must remain valid for backend calls. Before hosting publicly, configure HTTPS with Secure cookies and an explicit allowed origin (`COHERENT_ALLOWED_ORIGINS`); the current proxy targets the backend on localhost. Browser voice uses the browser's speech service and requires permission. Typed requests remain fully usable when voice is unavailable.

Live acceptance completed: all three Cognito client logins and the staff login, a Bedrock-assisted confirmed request, its DynamoDB document archive and staff visibility, profile persistence, logout, client isolation, draft restoration without automatic submission, and all four client screens at a 390px viewport. Printed request output was inspected as A4 pages with complete account values and history.

Production validation: `npm run build` passes with TypeScript checking enabled; all 150 Python tests pass. Seven legacy client browser tests passed during portal development. The client portal's live browser smoke also passes. The current local preview uses the production build (`cd web && npm run start -- --hostname 127.0.0.1 --port 3200`). Use the development command above when editing. The SQLite reference history is replaced from each client's cloud record so legacy seed events cannot contradict the portal's history.

### Portal and advisor integration

The portal and advisor workspace now run together. `/workspace/requests` includes current request status, advisor clarification messages, client replies, and separately saved A4 document snapshots. Cognito identity scopes both `/portal/*` and `/my/requests/*`; demo headers cannot switch the signed-in client. Staff review and replies preserve the immutable submission snapshot, including when cloud archiving is retried after a workflow update.

Merge validation: 150 Python tests and the production frontend build pass, including an authenticated advisor clarification/client reply regression that verifies client isolation and preservation of the original submission document.

## Six upgrades: verification, cited guidance, streaming, and accessible follow-up

1. **Independent Verifier.** Forge's nonempty fields carry source paths. Deterministic checks compare
   values, amounts, and masked accounts; a separate Bedrock call reviews the full packet and drafts for
   unsupported statements. The UI shows **pass / needs fix** and field coverage. A failed or unavailable
   audit withholds the ready packet and disables approval. The backend requires its own passing receipt
   for the exact current case fingerprint; editing a case invalidates old receipts. Approval records a
   history event; it does not execute a transaction or send a draft. Clarification messages are audited
   again when sent, and a compliance override cannot bypass a failed record audit. Pass means *no
   detected mismatch*, not a truth guarantee. Offline mode clearly labels deterministic-only checks.
2. **Sentinel retrieval and citations.** A real Bedrock KB indexes two curated public-guidance excerpts
   in `data/compliance/sources.json`: the [SEC Reg BI compliance guide](https://www.sec.gov/resources-small-businesses/small-business-compliance-guides/regulation-best-interest)
   and [IRS early-distribution guidance](https://www.irs.gov/retirement-plans/plan-participant-employee/retirement-topics-exceptions-to-tax-on-early-distributions).
   This is a deliberately small guidance corpus, **not the full regulations or a legal/suitability
   determination**. Retrieval uses category-only queries, without client records. Source IDs and
   excerpts must match the registered corpus. Model citations are checked against retrieved text,
   allowing whitespace and typographic-quote differences, and the UI displays the original excerpt.
   Missing retrieval or a failed model review produces an explicit needs-changes result; it never
   claims an uncited memory answer is RAG. The advisor checklist remains a human responsibility.
3. **Actual streaming and run evidence.** `POST /staff/cases/{id}/agents/stream` provides real Bedrock
   `ConverseStream` deltas, stage events, model ID, tools, cited sources, token usage, and elapsed time.
   No artificial stage timers or fabricated confidence percentages. Confidence is explicitly
   uncalibrated. Advanced output is model content/tool arguments, never hidden reasoning or prompts.
   Forge/reply stream content stays hidden until the Verifier passes; live stage and received-chunk
   progress remain visible. Other agents expose clearly marked provisional output. Cached/offline runs
   do not simulate tokens. Disconnects cancel delivery; four simultaneous runs and bounded queues cap
   stream work. A model request already in flight may finish before cancellation takes effect.
4. **Polly + voice.** Client questions/options and request-message threads have read-aloud buttons;
   “Read questions aloud” enables automatic playback. “Speak instead” uses browser speech recognition
   where supported. Starting the microphone stops playback; stop/cancel controls remain available.
   `/portal/speech` requires client authentication, accepts up to 2,500 characters, limits each client
   to 15 calls/minute per server process, and returns uncached MP3 audio. Text/audio are not saved by
   the app. Browser playback/microphone or AWS failures leave readable text and typing available.
   Long message threads are read up to the 2,500-character limit.
5. **Calm accessibility controls.** Larger text, stronger contrast, and read-aloud preferences persist
   locally. Large-text request columns reflow; controls have visible focus and descriptive labels.
   Persistent “No money has moved” reassurance and “Talk to a person” lead to a reviewed contact request,
   without placing a call or automatically submitting. This is tested accessibility support, not a WCAG
   conformance certification.
6. **Post-submit reply loop.** My requests explains the current state in plain words, displays advisor
   questions, and accepts the client's own-word reply. Status refreshes while the tab is visible and
   can be refreshed manually. Replies return to the staff record and queue. Archived A4 submission
   documents remain immutable; subsequent conversation lives in the case history.

### Provision the compliance KB and enable speech

With authorized AWS credentials in the normal SDK provider chain:

```bash
AWS_REGION=us-east-1 python scripts/provision_knowledge_base.py
```

The resumable script creates a private encrypted S3 document bucket, an S3 Vectors index (1,024
float32 dimensions, cosine distance), a scoped Bedrock service role, a Titan-v2-backed KB and S3 data
source, then waits for ingestion. IDs are saved to ignored `var/knowledge-base.json`. Re-run after
reviewing/updating corpus excerpts to sync them. The app reads this file automatically; override with
`COHERENT_KB_CONFIG` or `BEDROCK_KNOWLEDGE_BASE_ID`. `BEDROCK_MAX_TOKENS` defaults to 2048. Requirements include the verified boto3/botocore
1.43.108 SDK floor for the S3 Vectors storage configuration.
Provisioning needs S3, S3 Vectors, IAM, and Bedrock control-plane permissions; these are separate from
runtime permissions. Runtime needs `bedrock:Retrieve` for that KB, model invocation/streaming, and
`polly:SynthesizeSpeech` (see `infra/iam_policy.json`). Polly needs no resource provisioning. These
resources and usage incur AWS charges; they persist until deleted. Remove the KB/data source, vector
index/bucket, document objects/bucket, and dedicated service role when retiring this demo.

Local acceptance: 167 Python tests, seven legacy browser checks, and the production build passed.
Real KB ingestion completed with two indexed documents. The authenticated upgrade browser smoke
passed Polly playback, persistent accessibility controls at 390px, live Bedrock audits, cited retrieval,
and a complete advisor-clarification/client-reply loop. All three client logins and the staff login
also passed the existing cloud portal smoke. A live adversarial check blocked an invented claim
that a withdrawal had completed. Run regression and optional authenticated browser acceptance with:

```bash
python -m pytest -q
cd web && npm run build
# From repo root, with both servers running and private demo access configured:
NODE_PATH=/path/to/playwright/node_modules node tests/portal/upgrades.cjs
```

The upgrade smoke checks real Polly audio, persisted reading preferences and 390px layouts, a live
Bedrock audit, cited KB review, and one fictional clarification/reply loop. It creates synthetic test
history and stores screenshots only under `/tmp`. Credentials, sign-in passwords, generated AWS IDs,
and client documents remain outside Git. Audit receipts are process-local: restarting the backend
requires regenerating before approval. Existing SQLite case history remains local to this demo host;
DynamoDB stores portal profiles, financial records, and submission snapshots.
