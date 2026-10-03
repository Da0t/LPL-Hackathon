# SamePage Product and Development Specification

> **Status:** this is the original specification, written before the build when the product was called SamePage and the work was split across four branches ("Agent 1" to "Agent 4"). It is kept for the product reasoning and the factual boundaries. The product is now **Coherent**; [`README.md`](README.md) describes what is actually built.

SamePage helps people describe financial service needs in everyday language, verify which account they mean, and send a clear request to the right person. The first audience is older investors who prefer speaking or have trouble recalling financial terms, but the product is useful to anyone unfamiliar with wealth-management language. This specification defines the hackathon prototype, the product story, the data contracts, and the work that can be developed in parallel.

The product promise is: **A client can say “the retirement money from my old job,” and SamePage helps them reach the right advisor without guessing which account they meant.**

## Product opportunity and factual boundaries

The proposed flow is a new service-intake experience. We should not claim that every LPL client currently attends an initial staff meeting or fills out forms before seeing an advisor; that is an assumption about some possible journeys, not a verified universal LPL process. Pitch the problem as the friction created when a client cannot name the financial product or service they need and must repeat or clarify a request across channels.

LPL describes different advisor services and areas of expertise, including retirement, investment management, tax coordination, and estate planning. That supports a specialty-aware routing concept. It does **not** give us access to LPL's internal advisor directory, capacity, licenses, or assignment rules. The prototype will use a fictional advisor directory with fictional specialties and availability. Sources: [LPL guide to advisor types](https://www.lpl.com/investors/investment-essentials/finding-researching-advisors/types-of-financial-advisors.html), [LPL wealth-management services](https://www.lpl.com/join-lpl/managing-your-business/wealth-management-solutions.html).

The interface should reduce memory burden. The W3C's [research on cognitive accessibility in voice interfaces](https://www.w3.org/TR/coga-voice/) describes needs such as completing tasks without learning new terms or remembering several choices at once. Show at most three suggestions at a time, always include “None of these,” and offer human help. Do not assume an older client's age implies diminished capacity.

## What the product does

SamePage has two connected experiences.

1. **Client intake:** An authenticated client speaks or types a request. As complete phrases arrive, the intake agent proposes no more than three plain-language interpretations, explains unfamiliar terms on demand, and asks one focused question at a time. Suggestions are grounded in relevant account data. The client corrects and confirms the final interpretation.
2. **Staff triage:** A second agent converts the confirmed request into a structured case, applies category tags, and recommends a routing destination. A staff member sees the original words, confirmed facts, relevant account snapshot, flags, and eligible fictional advisors. The staff member assigns the case; the system does not silently select or contact an advisor.

The prototype creates and routes **service requests**. It does not recommend investments, execute transactions, open accounts, grant authority, determine taxes, diagnose cognitive impairment, or decide whether a client is being exploited.

## Business and acquisition thesis

SamePage would be sold as an intake and routing product for wealth-management firms, with LPL as a particularly strong potential acquirer because it already connects investor experiences with advisor workflows. The proposed product asset is more than a speech interface: it combines a plain-language financial vocabulary, account-grounded clarification, client confirmation, a structured case record, and human-reviewed routing. A generic transcription or meeting-summary feature does not provide that complete handoff.

The acquisition argument is that buying a focused product could let LPL integrate this workflow into its client and advisor experiences faster than starting from a blank slate. This is a **pitch hypothesis**, not evidence that LPL has decided to buy it or that no equivalent internal capability exists. LPL has announced both an investor application and AI work across advisor workflows, so integration into those surfaces is a plausible proposed path. [LPL Latitude announcement](https://investor.lpl.com/news-releases/news-release-details/lpl-financials-latitude-unifies-technology-built-future-advice)

To establish business impact after the hackathon, pilot SamePage against ordinary intake on three measures: median time from first request to correct destination, number of contacts needed to clarify a request, and the percentage of staff who override the suggested category or advisor. Add a client comprehension question after review: “Is this what you meant?” The prototype will demonstrate the measurement points, not claim unmeasured savings or retention gains.

## Core client journey

| Step | Client sees | System action |
| --- | --- | --- |
| Open intake | “Tell us what you need help with” and microphone/type controls | Load a minimal authorized client profile and account list. A guest or unauthenticated user gets general definitions only. |
| Describe need | Live transcript or typed text, with large editable text | Speech is transcribed or text is accepted. Stable phrases trigger the intake agent; partial words do not. |
| Explore meaning | Up to three large suggestion cards, “None of these,” and “Talk to a person” | Agent compares the phrase with account labels, types, and relevant history. It never treats a suggestion as a fact. |
| Clarify | One question at a time, with “Why am I being asked?” | Agent resolves account and intent ambiguity. If it cannot, the case remains unresolved and goes to staff. |
| Understand terms | Short explanation next to a term such as “rollover IRA” | Definition comes from an approved glossary and distinguishes general explanation from personalized advice. |
| Review request | Plain-language summary, chosen account, requested amount if stated, and remaining questions | Client edits or confirms. Submission requires confirmation; no inferred amount or account is silently accepted. |
| Submit | Case number and what happens next | Store the confirmed case and show a status. Do not promise an appointment or completion time the prototype cannot deliver. |

**Demonstration scenario:** A fictional client says, “I need six thousand dollars for my husband's care. It's in the Roth thing from my old job.” The synthetic profile contains a rollover IRA from that employer and no Roth IRA. SamePage responds, “I don't see a Roth IRA in these records. Could you mean your rollover IRA from your former employer?” It explains “rollover IRA” simply, asks whether the client wants to discuss a withdrawal or merely understand options, then asks the client to confirm the final wording. The advisor receives the confirmed request, not an invented Roth IRA transaction.

For this scenario, the account balance and prior rollover event appear only after the account has been identified and only in the authorized staff view. The client review screen can show the selected account's familiar label and masked identifier. A historical event is included only when it helps explain which account the client meant or what staff needs to do.

## Client dashboard

The main screen has a large central microphone button and an equally visible typing field. The transcript remains editable. Suggestion cards sit immediately below the latest phrase, not in a separate chat log. A client can pause, replay, select “None of these,” or ask for a person at any time. Avoid jargon in navigation and avoid a dense account table during intake.

After clarification, the screen changes to a review page with four blocks: “What you told us,” “What we understood,” “Account we think you mean,” and “Questions for your advisor.” The client can correct each block. A final button says **Confirm and send request**.

Accessibility defaults are large type, strong contrast, keyboard operation, visible transcript, and a text path with the same functionality as voice. Speech and text should be interchangeable within one session. Do not score speech fluency or infer cognitive status.

## Staff dashboard and advisor assignment

The staff dashboard has a queue with case ID, creation time, status, category, urgency flag, current advisor relationship, and whether clarification is still needed. Opening a case shows the two-page equivalent below. The staff view can filter by category and show why each advisor is recommended.

The fictional advisor directory includes `advisor_id`, display name, specialty tags, state/region, meeting mode, capacity, availability, existing-client relationship, and active status. Do not claim these fictional fields mirror a live LPL system.

Routing order for the prototype:

1. If the request concerns suspected fraud, unauthorized access, or account takeover, recommend a **security or specialist review queue** for staff review. Do not send it directly to a general planning advisor.
2. Otherwise, show the client's existing advisor first if that advisor is active and the configured workflow permits it.
3. Rank other fictional advisors by required specialty match, availability, meeting preference, and capacity. Treat license/state eligibility as a required manual or verified-system check, not an AI guess.
4. Show the top two or three candidates and a reason for each. Staff chooses an advisor or changes the destination and records a reason.

Category tags are structured labels, not arbitrary “buzzwords.” The first taxonomy is `retirement_income`, `withdrawal_or_distribution`, `rollover_or_transfer`, `beneficiary_or_estate`, `investment_planning`, `account_service`, `fraud_or_security`, and `other_or_unclear`. One case may have multiple tags. The routing recommendation cites the confirmed client request and the directory fields it used.

## Case document format

The case is a structured record rendered in two views. This prevents a polished AI paragraph from hiding missing or uncertain facts. The prototype may export a PDF later, but a reviewable on-screen document is sufficient for the working demo.

**Page 1: Request and routing**

- Case ID, submission time, client display name, preferred contact channel, and status.
- Client's original words, clearly labeled as a transcript or typed text.
- Confirmed plain-language request, written for the client.
- Staff summary using appropriate financial terminology, such as “Discuss potential distribution from rollover IRA.” This is a description of the question, not advice to take that action.
- Confirmed goal, amount **only if stated and confirmed**, timing, selected account, and unresolved questions.
- Category tags, urgency reason if any, recommended destination, and why.
- Client confirmation time and staff review/assignment history.

**Page 2: Relevant account context**

- Account type and name, masked identifier, ownership/relationship as recorded, available balance snapshot and its **as-of time**, if authorized and relevant.
- Relevant prior events, such as a synthetic rollover or prior service request, each with a date and source record ID.
- Facts that conflict with the client's wording, such as “Client said Roth IRA; no Roth IRA appears in the authorized account list.”
- Data gaps and cautions, such as “Tax effects have not been assessed.”
- Sources for each account fact. An AI-generated statement without a source must not appear as an account fact.

Example machine-readable case fields:

```json
{
  "case_id": "CASE-1042",
  "client_id": "CLIENT-017",
  "status": "submitted",
  "input_mode": "voice",
  "original_words": "I need six thousand dollars from the Roth thing from my old job.",
  "confirmed_plain_language_request": "I want to speak with an advisor about using $6,000 from my retirement account from my former employer.",
  "staff_summary": "Client requests discussion of a possible $6,000 distribution from a rollover IRA for care expenses.",
  "intent": "discuss_possible_withdrawal",
  "amount_requested": 6000,
  "currency": "USD",
  "selected_account_id": "ACCT-201",
  "account_match_status": "client_confirmed",
  "categories": ["withdrawal_or_distribution", "retirement_income"],
  "unresolved_questions": ["Desired timing", "Potential tax implications for advisor review"],
  "flags": ["client_term_did_not_match_account_type"],
  "account_context": {
    "account_type": "rollover_ira",
    "masked_identifier": "****4821",
    "balance": 84000,
    "balance_as_of": "2026-10-01",
    "relevant_events": [{"type": "rollover", "date": "2023-06-12", "source_id": "EVENT-09"}]
  },
  "routing": {
    "destination": "retirement_advisor_review",
    "recommended_advisor_ids": ["ADV-03", "ADV-01"],
    "assigned_advisor_id": null,
    "staff_decision": null
  }
}
```

All names, dates, amounts, identifiers, and events in the demo are fictional. The example balance is context for staff, **not** a claim that $84,000 is available to withdraw or that any withdrawal is appropriate.

## AI agents and application services

**Intake agent:** Reads a stable phrase and the smallest authorized client context needed to interpret it. Returns candidate meanings, one next question, a short glossary explanation if requested, and explicit uncertainty. It can call `get_relevant_accounts(client_id, phrase)` and `get_approved_definition(term)`. It may not create a final case or infer a missing amount.

**Triage agent:** Runs only after client confirmation. It extracts fields into the case schema, assigns category tags, flags contradictions or missing details, and recommends a queue or fictional advisor candidates. It can call `get_relevant_account_history(account_id)` and `search_advisor_directory(categories, preferences)`. A schema validator rejects unsupported account facts, unknown category tags, or missing source IDs.

These are two **logical stages** that may share one Bedrock model and one backend process. Run them sequentially and pace calls around the event account's approximate one-call-per-second Bedrock limit. This meets the requested “second agent” behavior without requiring a complex multi-agent runtime. Deterministic application code handles authentication, data access, matching constraints, case status, and assignment; the model handles language interpretation and explanation.

State transitions: `draft` → `needs_clarification` or `ready_for_client_review` → `submitted` → `staff_review` → `assigned`. Staff can move a submitted case to `needs_client_followup`. Failed transcription or model calls preserve the draft and offer typing or human help.

## AWS architecture and exact jobs

The application runs in **us-east-1**, as required by the hackathon brief.

| Component | Hackathon choice | Job and reason |
| --- | --- | --- |
| Interface | FastAPI serving two small HTML/CSS/JavaScript pages | Give the client and staff developers separate files while keeping one local origin and a simple backend. Browser speech recognition may provide prototype microphone input; label it accurately if used. |
| Language agent | **Amazon Bedrock**, with one generation-capable model from the brief's allowlist | Interpret plain language, ask clarifying questions, draft the two summaries, and classify the confirmed request. Verify the actual model ID and access in the event account before coding against it. |
| Speech | **Amazon Transcribe Streaming**, if the team can complete it reliably | Produce live speech-to-text for the microphone experience. AWS documents real-time transcription through SDKs, HTTP/2, and WebSockets. A typed path remains fully functional. [AWS documentation](https://docs.aws.amazon.com/en_en/transcribe/latest/dg/streaming.html) |
| Case data | Local SQLite for the first working demo; **Amazon DynamoDB** only if the team has account setup time | Share submitted cases and staff assignments between views. DynamoDB is a valid later adapter, but Bedrock alone already meets the at-least-one-AWS-service requirement. |
| Optional storage | No S3 needed for the core demo | Avoid an unnecessary service. If audio or exports are stored in S3 later, keep the bucket private. |

For the fastest reliable demo, implement typed intake first, then microphone input. A short push-to-talk utterance followed by suggestions is an acceptable first prototype if continuous streaming proves unstable; describe that behavior accurately in the presentation. The final product vision can support uninterrupted streaming. Do not hard-code keys. Use the event account's supported credential mechanism, least-privilege IAM, and synthetic data only.

## API contracts for parallel development

The four development agents should use **FastAPI on port 8000** with separate static client and staff pages. The version-one HTTP contract is frozen in `contracts/API_V1.md`, with fictional examples in `contracts/demo_fixture_v1.json` and a standalone mock at `contracts/mock_api.py`. The paths below summarize that contract. Build against the frozen fields; do not wait for another agent's implementation.

- `POST /intake/start` with `{client_id}` → `{session_id, client_display_name, status}`.
- `POST /intake/{session_id}/turn` with `{text, input_mode, selected_option_id?}` → `{session_id, transcript, suggestions, question, definitions, candidate_intent, selected_account_id, uncertainty, status}`. A suggestion is `{id, label, account_id?}`; a definition is `{term, plain}`. `suggestions` has no more than three items.
- `POST /intake/{session_id}/confirm` with `{confirmed_plain_language_request, selected_account_id?, amount_requested?}` → `{case_id, status, client_summary}`. The backend validates any account and amount against the conversation and client selection.
- `GET /staff/cases` → `{cases: [{case_id, client_display_name, created_at, status, categories, flags, confirmed_plain_language_request}]}`.
- `GET /staff/cases/{case_id}` → the complete case record in the example schema above, including original words, source references, and only relevant account context.
- `GET /staff/cases/{case_id}/candidates` → `{candidates: [{advisor_id, display_name, specialties, available, reason}]}`.
- `POST /staff/cases/{case_id}/assign` with `{advisor_id, staff_reason}` → `{case_id, status, assigned_advisor_id}`.

On model errors, `/turn` returns the preserved draft with `status: "needs_clarification"`, an explanation, and a way to continue typing or contact a person. Error responses use `{error_code, message}`. Agent 1's AWS adapter exposes `intake_turn(client_id, transcript, selected_option_id, tools) -> dict` and `triage_case(confirmed_request, tools) -> dict`. Agent 2 supplies `tools` and validates the returned dictionaries. The Bedrock adapter never reads storage directly; the backend supplies authorized tool callbacks.

Every request is scoped to a role and client/case ID. For the hackathon, use a visible **demo role switcher** over synthetic records and label it as simulated access control. Do not present this as production authentication.

## Synthetic demo data

Create three fictional clients, six to eight accounts, two or three prior events per relevant account, eight fictional advisors, and four cases. The core cases are: ambiguous former-employer account, a clear Roth IRA question, a beneficiary change request, and a possible unauthorized-access concern that goes to a specialist queue. Include balances and history only for cases where they make the request clearer. No real client, advisor, account, or market data may enter the prototype.

The data seed should contain a glossary of ten common terms with plain explanations, including Roth IRA, rollover IRA, brokerage account, beneficiary, transfer, withdrawal, distribution, required minimum distribution, advisor, and trusted contact. Definitions should be approved text in a local file; the agent selects and contextualizes them rather than improvising legal or tax rules.

## What counts as a working demo

1. A client types or speaks the ambiguous “Roth thing from my old job” request.
2. Suggestions appear, and the agent notices that no Roth IRA exists in the synthetic profile.
3. The agent asks one clarifying question, provides a plain-language term explanation, and lets the client correct it.
4. The client confirms the request. A structured case is created with the original wording, confirmed wording, account snapshot, source record, tags, and unresolved questions.
5. The staff queue updates. A staff member opens the case, sees two suitable fictional advisors with reasons, and assigns one.
6. A second demo case with a security flag routes to specialist review rather than a retirement advisor.

The presentation must identify what is live and what is simulated. The demo does not need a real LPL integration, automatic scheduling, PDF export, or actual financial transaction.

## Development work packages

| Work package | Owns | Deliverable |
| --- | --- | --- |
| Agent 1 AWS | Bedrock agent adapter, allowed-model verification, IAM/configuration, call pacing, optional Transcribe | Live Bedrock interpretation and triage with no embedded credentials. |
| Agent 2 backend | FastAPI contract, authorized tools, state machine, local case storage, validation and assignment | Stable endpoints and a submitted case from the core scenario. |
| Agent 3 client interface | Microphone/text input, suggestions, clarification, glossary, review and confirmation | A client can complete the entire intake flow using text even if speech fails. |
| Agent 4 staff and data | Synthetic profiles/accounts/history/advisors, queue, case document, assignment screen, demo script | Staff can review, override, and assign a submitted case using coherent fictional records. |

Integrate against the API contracts early. Keep one known-good synthetic client and request unchanged for the final demo. Verify the microphone, model access, and region on the machine that will present.

## Four agent coordination protocol

Each teammate gives one file from `agent-briefs/` to their development agent and works in a **separate clone or worktree** on the named branch. Agents do not share chat memory, so the brief, this specification, `contracts/API_V1.md`, `contracts/demo_fixture_v1.json`, and merged Git commits are the shared context. No agent should rely on a decision made only in its own conversation.

The frozen contract, fixture, and mock API let every agent start independently. Agent 1 can use fixture-backed tool callbacks; Agent 2 can use a temporary local AI stub; Agents 3 and 4 can call the mock API on port 8001. Agent 1 owns AWS integration, Agent 2 the real backend, Agent 3 the client page, and Agent 4 the staff page plus expanded seed data. When a field or endpoint truly must change, propose a version-two contract to the team and coordinate adoption; do not silently edit version one. Each agent pushes a branch and opens a pull request; a teammate acting as integrator merges them into `main` after checking that owned paths do not conflict.

At each milestone, every agent reports four facts to the team: branch and commit, what works, contract or fixture changes, and blockers. After each merge, the other agents pull `main` and rerun their own flow. Before the deadline, run one integrated rehearsal from client speech or text through staff assignment, then reset and repeat on the presentation machine.

## Requirement check and remaining gaps

| Hackathon requirement | SamePage status |
| --- | --- |
| Meaningful wealth-management problem for investors, advisors, or support teams | **Met by concept:** unclear requests and account identification affect both clients and staff. The demo must show the problem and resulting case. |
| AI-powered working agent | **Met when built:** intake and triage stages use Bedrock and tools for account lookup, glossary, history, and advisor search. A static mockup would not qualify. |
| At least one AWS service | **Met when built:** Bedrock is essential. Transcribe and DynamoDB have distinct optional jobs. |
| Approved models only | **Open until verified:** choose a generation model on the brief's allowlist and confirm its actual Bedrock model ID and access in `us-east-1`. Do not assume a name in the brief guarantees an enabled model ID. |
| Synthetic data only | **Design meets:** seed all clients, accounts, balances, advisors, and events with fictional data. Audit the final demo and code ZIP. |
| Private S3 and safe credentials | **Design meets:** no S3 in the core; if added, bucket must remain private. Use IAM and no hard-coded secrets. |
| Startup acquisition story | **Met by concept:** an accessible intake and routing layer could plug into LPL investor and advisor experiences; claim it as a proposed acquisition opportunity, not an existing LPL gap proven by this prototype. |
| Two main awards | Select **Startup We'd Buy Tomorrow** and **Biggest Business Impact** as the team specified. Best Use of AWS is automatic. |
| Working prototype, LPL template deck, code ZIP, submission form, deadline | **Open deliverables:** build, validate, package, and submit by **October 3, 2026, 9:00 AM PT**. Remain available for judging. |

The largest product risk is an AI guess becoming a false account fact. Make uncertainty visible, require client confirmation for account and amount, retain the client's original wording, and require staff approval for routing. The largest build risk is live speech; keep the text path complete and working before adding streaming.

## Five-minute pitch sequence

1. **Problem:** “A client knows what life problem they have but not the financial term. That gap creates repeated explanations and the risk of misunderstanding.”
2. **Product:** “SamePage translates everyday language into a confirmed service request, grounded in the client's own accounts.”
3. **Live reveal:** Client says “Roth thing from my old job”; agent finds no Roth IRA and asks the right question instead of guessing.
4. **Staff handoff:** Show the completed case, relevant account history, category tags, and human-approved advisor match.
5. **Business and AWS:** LPL could scale clearer intake across clients and advisors. Bedrock interprets and classifies; Transcribe handles speech if implemented; case storage supports the queue. Measure time to a correctly routed request, number of clarification contacts, and staff override rate in a future pilot. These are proposed metrics, not measured hackathon outcomes.

The final line is: **“SamePage lets clients speak in their own words and gives advisors a request they can trust.”**
