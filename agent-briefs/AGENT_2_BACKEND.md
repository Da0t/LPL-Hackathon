# Agent 2 Backend API and Case Logic

You are one of four parallel development agents building SamePage for the LPL hackathon. **You own the backend API, application state, authorization boundary for the demo, case validation, and the shared API contract.** Work in your own clone or worktree of [Da0t/LPL-Hackathon](https://github.com/Da0t/LPL-Hackathon) on branch `codex/agent2-backend`. First read `HACKATHON_PROJECT_BRIEF.md` and `SAMEPAGE_PRODUCT_SPEC.md`. Agent 1 owns all AWS work; Agents 3 and 4 own the two interfaces.

## Your mission

Build a small FastAPI app that accepts a client request, calls Agent 1's Bedrock adapter, stores a confirmed case, serves the client and staff pages, and supports human-reviewed advisor assignment. The typed flow must work from start to assignment before optional speech work is added.

## Files you own

- `backend/main.py`, `backend/api.py`, `backend/schemas.py`, and `backend/services/`: HTTP routes, validation, state machine, deterministic routing rules, and static page serving.
- `backend/store.py` and local SQLite setup for synthetic clients, accounts, cases, and assignments. Agent 4 owns the seed data files; read them without modifying them.
- `requirements.txt`, `README.md`, and `tests/backend/`: app dependencies, run instructions, and meaningful API tests.
- The **API contracts** section of `SAMEPAGE_PRODUCT_SPEC.md` if and only if all teammates are notified before a change.

Do not edit `backend/aws/` (Agent 1), `frontend/client/` (Agent 3), `frontend/staff/` or `data/` (Agent 4). Serve those paths even if their files are still being built.

## Frozen HTTP contract

Implement the exact paths and field names in the product spec:

```text
POST /intake/start
POST /intake/{session_id}/turn
POST /intake/{session_id}/confirm
GET  /staff/cases
GET  /staff/cases/{case_id}
GET  /staff/cases/{case_id}/candidates
POST /staff/cases/{case_id}/assign
```

Serve `/client` and `/staff` from the separate frontend directories on the same origin, port 8000. Give Agents 3 and 4 a temporary in-memory stub for every endpoint **early**, before the live AWS adapter is integrated. Their pages should be able to develop against these responses.

Agent 1 exposes `intake_turn(client_id, transcript, selected_option_id, tools) -> dict` and `triage_case(confirmed_request, tools) -> dict`. Supply the authorized tool callbacks. Validate the returned dictionaries against the case schema; the model is not a source of account facts. Account balances, types, and history come only from Agent 4's synthetic records with source IDs and as-of dates.

## Deterministic rules you own

- `client_id` must come from the active synthetic demo session; the client cannot request another client's account IDs. The visible role switcher is **simulated access control**, not production authentication. Staff endpoints require the staff demo role.
- A model suggestion is a proposal. Do not mark an account as selected or an amount as confirmed until the client explicitly chooses or edits it on the review screen.
- A confirmed case retains the original words, client-approved wording, selected account or unresolved marker, staff summary, categories, flags, and source references.
- If the case indicates possible fraud, unauthorized access, or account takeover, recommend the specialist review queue rather than a general advisor. Staff still makes the final decision.
- Rank advisor candidates using the fictional directory: existing relationship when applicable, specialty match, availability, meeting preference, and capacity. Do not let the model invent licensing or state eligibility.
- A model or AWS error preserves the draft and returns a useful message. `assign` records the staff member's selected advisor and reason. No outbound message, transaction, appointment, or real LPL system call occurs.

## Build order and definition of done

1. Publish working endpoint stubs and JSON examples to Agents 3 and 4; confirm the agent adapter signatures with Agent 1.
2. Load Agent 4's synthetic seed data into local SQLite or a simple local repository. Avoid requiring DynamoDB for the first integrated demo.
3. Implement intake state and confirmation, then triage and staff queue, then candidate ranking and assignment.
4. Swap endpoint stubs for Agent 1's live Bedrock adapter. Keep an explicit mock mode for offline UI development, but the final judged path must use Bedrock.
5. Run a full synthetic end-to-end test for ambiguous IRA, clear request, and specialist security routing. Record one-command startup and demo reset in `README.md`.

Done means a client request submitted through the API appears in the staff queue, displays supported account facts, and can be manually assigned. The core path must work with typed input and live Bedrock.

## Synchronization with the other agents

The version-one contract in `SAMEPAGE_PRODUCT_SPEC.md` is the shared source of truth. You are its editor, but changes require a message to Agents 1, 3, and 4 before they depend on it. Prefer additive fields over breaking changes. Push your branch and open a pull request; do not push directly to `main`. Send the team your branch/commit, endpoint status, contract changes, and blockers at each milestone. Pull merged `main` before the final integration run. Keep the spec, implementation, and examples consistent.
