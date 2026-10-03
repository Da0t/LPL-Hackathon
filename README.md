# Coherent

**Coherent turns everyday language into a confirmed, correctly routed wealth-management request, and
hands the advisor a ready-to-act brief.** A client can say *"I need six thousand dollars from the Roth
thing from my old job"*; Coherent notices there is no Roth account, surfaces the real rollover IRA,
confirms what the client meant, and routes a structured request to the right advisor, who opens it to
a Bedrock-generated prep brief instead of a cold transcript.

Built for the **2026 LPL Financial University Hackathon**. Awards targeted: *Startup We'd Buy
Tomorrow* and *Biggest Business Impact*, plus the automatic *Best Use of AWS*.

> All data is synthetic. The role switcher is **simulated** access control, not production auth. No
> real LPL system, transaction, appointment, or message ever occurs.
>
> Note: the product is **Coherent**. Some internal identifiers kept from the original codebase still
> read `samepage` (e.g. the `SAMEPAGE_AI_MODE` env var, `backend/aws`); those are technical names, not
> the product.

**Documentation maintenance:** update this README whenever a significant feature, workflow,
infrastructure, configuration, or validation procedure changes. Describe the behavior available on
the current branch and clearly identify work that is still awaiting integration.

---

## The demo in 60 seconds

1. **Client intake** (`/intake`) , a client speaks or types a loose request. Amazon Bedrock proposes
   up to three plain-language interpretations grounded in the client's real accounts, normalizes
   shorthand/acronyms to approved terms ("R O I" -> *return on investment*, "the tax form" ->
   *1099-R*), and asks one question at a time, never inventing an account or amount. A live **routing
   graph** blooms as it interprets.
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
recorded override. Clients see their own requests and clarification messages in the intake page's
My requests view, and can reply while a request is waiting on them. A reply returns the case to its
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
       web/ /intake (Next.js)                     web/ /dashboard (Next.js)
              │        live routing graph                  │  AI prep brief + actions
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
account snapshot, security route, and advisor ranking is deterministic application code, so a
confident-but-wrong model answer can never become a false account fact.

---

## How we use AWS

- **Amazon Bedrock (Converse API + native tool use), three surfaces.** (1) Intake + triage interpret the
  client's words and classify the request through narrow, client-scoped tools with schema-forced
  output. (2) A read-only **advisor prep brief** turns a confirmed case into talking points, facts to
  confirm, and compliance cautions. (3) Four **advisor agents** (reply drafter, compliance reviewer,
  next-steps planner, security investigator). Each is a single Bedrock call that must answer through
  one tool with a fixed schema, and each has a deterministic offline fallback. There is no
  orchestration framework: the only loop is draft, review, one revision, review, run by plain code
  in `backend/services/reply_workflow.py`. Right-sized model: **Claude Haiku 4.5** (`us.anthropic.claude-
  haiku-4-5-20251001-v1:0`), swappable via `BEDROCK_MODEL_ID`.
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
  SAMEPAGE_AI_MODE=bedrock \
  python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

`SAMEPAGE_AI_MODE=mock` runs everything offline with deterministic responses.

**2. Frontend** (the demo UI):

```bash
cd web
pnpm install
PORT=3200 pnpm dev          # use 3200, not 3000 (a stale service worker hijacks 3000)
```

Open **http://localhost:3200** , `/` (landing), `/intake` (client), `/dashboard` (advisor). See
[`web/README.md`](web/README.md).

**Tests:** `python -m pytest` (backend + AWS adapter + term matching).

The follow-up workflows have regression coverage in `tests/backend/test_advisor_workspace.py`,
`test_reply_workflow.py`, and `test_workspace_followups.py`; advisor agent output validation is in
`tests/aws/test_advisor_agents.py`.

### Client portal awaiting integration

The authenticated client portal is pushed on `codex/client-portal` in
[PR #9](https://github.com/Da0t/LPL-Hackathon/pull/9), and is not yet part of `main`.
That branch replaces the client picker with Cognito sign-in, editable personal and financial
profiles, three fictional clients with 16 accounts and 154 history records, and a three-column
request workspace with printable A4 documents. DynamoDB stores client records and submitted
document snapshots; the case workflow remains in local SQLite.

Use the README on that branch for provisioning and startup instructions. Its private demo sign-ins
are generated in ignored `var/demo-access.json`; AWS credentials and passwords must stay out of Git.
The `/login` and `/workspace` routes and real AWS authentication belong to that branch. The `main`
startup instructions above still describe the simulated-access demo. After changing branches,
restart the backend and rebuild/restart any production frontend preview to display that checkout.

---

## Repository structure

```
LPL-Hackathon/
├── web/                     THE demo , Coherent frontend (Next.js + Geist + Tailwind)
│   ├── app/                 page.tsx (landing), intake/, dashboard/, layout.tsx, globals.css
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
│   ├── store.py             SQLite repository + seed loader
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
- **Simulated:** the demo role switcher, and every client, account, balance, event, and advisor.
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
