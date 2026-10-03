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
   proposed fields, compliance checks, and a draft message. The independent Verifier must pass before
   the prepared reply is shown; the final edited message is checked again when sent.
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

- **Amazon Bedrock (Converse / ConverseStream with native tool use).** Intake and triage interpret the client's
  words and classify the request through narrow, client-scoped tools with schema-forced output. On
  the advisor side, Bedrock prepares the action packet and the prep brief and runs four **advisor
  agents** (reply drafter, compliance reviewer, next-steps planner, security investigator). Each
  agent answers through a fixed tool schema. A separate Verifier call audits the packet and drafts;
  live audit failures block approval. Other agents have visibly labeled offline fallbacks. There is no orchestration framework: the only loop is draft,
  review, one revision, review, run by plain code in `backend/services/reply_workflow.py`. The model
  is **Claude Haiku 4.5** (`us.anthropic.claude-haiku-4-5-20251001-v1:0`), swappable via
  `BEDROCK_MODEL_ID`.
- **Bedrock Knowledge Bases, S3 Vectors, and Titan v2.** Sentinel retrieves and cites reviewed SEC/IRS
  guidance. The corpus is limited to two public excerpts; it is not a legal determination.
- **Amazon Polly.** Authenticated neural read-aloud for questions, options, and client message threads.
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

### AWS hosted demo

`python -m scripts.deploy_aws` deploys the **pushed main commit** to a dedicated Amazon Linux 2023
EC2 instance in `us-east-1`. It reuses the existing Cognito pool, DynamoDB table, and indexed Bedrock
Knowledge Base. It creates a scoped EC2 role, encrypted 30 GB EBS root disk, static public address,
security group accepting only the CloudFront origin-facing prefix list, and a CloudFront distribution
with an HTTPS demo URL. The web and API servers run as systemd services and are updated through AWS
Systems Manager. No long-lived AWS key is copied to the host; the role supplies credentials. The
origin also requires a private header set by this CloudFront distribution. Login cookies are `Secure`
on the hosted URL. CloudFront forwards cookies, headers, query strings, and all request methods with
caching disabled, so authenticated responses are not shared.

First complete the existing portal and Knowledge Base provisioning below, then run this from a clean,
pushed `main` checkout with your authorized AWS session available to boto3:

```bash
AWS_SHARED_CREDENTIALS_FILE=/path/to/your/private-aws-session \
AWS_DEFAULT_REGION=us-east-1 .venv/bin/python -m scripts.deploy_aws
```

The resumable script records resource IDs in ignored `var/deployment-aws.json` and prints the HTTPS
URL after the host and CloudFront are ready. Re-run it after pushing a new main commit to rebuild the
host. Check the public `/login` and `/api/health` paths, then sign in with the private demo identities
in `var/demo-access.json`. The deployment uses the same fictional accounts and cloud portal records as
the local app. The case SQLite file is separate on the instance's EBS disk; it survives reboot and
restart. Do not terminate the instance if you need its case history.

This is a **single-instance hackathon deployment** with synthetic data. It has no automatic failover
or database backup. CloudFront provides HTTPS to the browser; its connection to the CloudFront-only
origin currently uses HTTP. Set up a domain, origin TLS, backups, monitoring, and a shared transactional
case store before treating this as a production financial application. EC2, EBS, the public IPv4
address, CloudFront, Bedrock, Knowledge Base, DynamoDB, and Polly can incur ongoing charges. The
AWS [CloudFront origin prefix list](https://docs.aws.amazon.com/vpc/latest/userguide/working-with-aws-managed-prefix-lists.html)
and [cache/origin request policies](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/controlling-origin-requests.html)
are described in AWS documentation.

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

- `/`: animated Coherent logo, a replayable example showing a client's words become a confirmed
  request record, and the technology logo strip.
- `/login`: email and password sign-in with a simplified typographic welcome panel.
- `/workspace`: overview with asset and cash snapshots, accounts, and recent activity.
- `/workspace/profile`: editable identity, contact, employment, household finances, goals, and
  trusted contact. Contact email and sign-in email are intentionally separate.
- `/workspace/finances`: accounts, holdings, editable account details, searchable history, account
  creation, and past-activity entry. Facts a client enters are marked as self-reported; entering a
  transfer never moves money or changes a balance.
- `/workspace/requests/new`: a step-by-step editor for the client's words, account clarification,
  and review of an A4-proportioned request document. The document carries the client's name, the description, the
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
  triage, the action packet, the prep brief, the advisor agents, and the independent record critic.
  Bedrock KB retrieval and Polly read-aloud are also live AWS calls.
- **Always deterministic:** authorization scope, account facts and sources, security routing, advisor
  ranking, queue priority, field comparisons, verdict calculation from reviewer findings, case state,
  assignment, and workflow actions. Model-generated checks and findings are not deterministic.
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

## Six upgrades: verification, cited guidance, streaming, and accessible follow-up

1. **Independent Verifier.** Forge's nonempty fields carry source paths. Deterministic checks compare
   values, amounts, and masked accounts; a separate Bedrock call reviews the full packet and drafts for
   unsupported statements. The UI shows **pass / needs fix** and field coverage. A failed or unavailable
   audit withholds the ready packet and disables approval. The backend requires its own passing receipt
   for the exact current case fingerprint; editing a case invalidates old receipts. Approval records a
   history event and sends the reviewed message to the client thread when supplied; it never executes
   a financial transaction. The final edited message is independently audited again before delivery. Clarification messages are audited
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
`COHERENT_KB_CONFIG` or `BEDROCK_KNOWLEDGE_BASE_ID`. `BEDROCK_MAX_TOKENS` defaults to 2048. The Next.js API proxy allows 120 seconds so the
backend can finish its bounded model calls or return its own timeout response. Requirements include the verified boto3/botocore
1.43.108 SDK floor for the S3 Vectors storage configuration.
Provisioning needs S3, S3 Vectors, IAM, and Bedrock control-plane permissions; these are separate from
runtime permissions. Runtime needs `bedrock:Retrieve` for that KB, model invocation/streaming, and
`polly:SynthesizeSpeech` (see `infra/iam_policy.json`). Polly needs no resource provisioning. These
resources and usage incur AWS charges; they persist until deleted. Remove the KB/data source, vector
index/bucket, document objects/bucket, and dedicated service role when retiring this demo.

Local acceptance: 188 Python tests, seven legacy browser checks, and the production build passed.
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
