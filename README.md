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
   TWO live Bedrock surfaces:             clients · accounts · events
   (1) intake_turn / triage_case         advisors · glossary · cases
   (2) advisor prep brief
   (+ Transcribe custom vocabulary, Guardrails hook)
```

The language model only **interprets, classifies, and briefs**. Every fact, authorization check,
account snapshot, security route, and advisor ranking is deterministic application code, so a
confident-but-wrong model answer can never become a false account fact.

---

## How we use AWS

- **Amazon Bedrock (Converse API + native tool use), two surfaces.** (1) Intake + triage interpret the
  client's words and classify the request through narrow, client-scoped tools with schema-forced
  output. (2) A read-only **advisor prep brief** turns a confirmed case into talking points, facts to
  confirm, and compliance cautions. Right-sized model: **Claude Haiku 4.5** (`us.anthropic.claude-
  haiku-4-5-20251001-v1:0`), swappable via `BEDROCK_MODEL_ID`.
- **Safety by construction** , the adapter injects authorized ids (never the model's), drops invented
  accounts, forces fraud cases to specialist review, and never asserts balances/history. Optional
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
│   ├── main.py api.py       app + routes (v1 contract + /brief and /action advisor endpoints)
│   ├── services/            intake, triage, staff (brief + actions), routing, tools, validation
│   ├── store.py             SQLite repository + seed loader
│   └── aws/                 Amazon Bedrock adapter (intake_turn, triage_case, advisor_brief), config, transcribe
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
  normalization, triage, and the advisor prep brief , Amazon Bedrock.
- **Always deterministic:** authorization scope, account facts and sources, security routing, advisor
  ranking, case state, assignment, and the workflow/lifecycle actions.
- **Simulated:** the demo role switcher, and every client, account, balance, event, and advisor.

## Documentation

- [`web/README.md`](web/README.md) , frontend run + structure
- [`AWS_SETUP.md`](AWS_SETUP.md) , AWS setup, model verification, smoke test
- [`contracts/API_V1.md`](contracts/API_V1.md) , frozen HTTP contract (advisor `/brief` and `/action` are additive)
- [`SAMEPAGE_PRODUCT_SPEC.md`](SAMEPAGE_PRODUCT_SPEC.md) · [`HACKATHON_PROJECT_BRIEF.md`](HACKATHON_PROJECT_BRIEF.md) · [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md)
