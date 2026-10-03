# Agent 2 Backend API and Case Logic

You are one of four parallel development agents building SamePage for the LPL hackathon. **You own the backend API, application state, demo authorization boundary, and case validation.** Work in your own clone or worktree of [Da0t/LPL-Hackathon](https://github.com/Da0t/LPL-Hackathon) on branch `codex/agent2-backend`. First read `HACKATHON_PROJECT_BRIEF.md`, `SAMEPAGE_PRODUCT_SPEC.md`, `contracts/API_V1.md`, `contracts/demo_fixture_v1.json`, and `INTEGRATION_RUNBOOK.md`. The contract and fixture are already frozen, so start independently without waiting for another agent. Agent 1 owns AWS; Agents 3 and 4 own the interfaces.

## Your mission

Build a small FastAPI app that accepts a client request, calls Agent 1's Bedrock adapter, stores a confirmed case, serves the client and staff pages, and supports human-reviewed advisor assignment. The typed flow must work from start to assignment before optional speech work is added.

## Files you own

- `backend/main.py`, `backend/api.py`, `backend/schemas.py`, and `backend/services/`: HTTP routes, validation, state machine, deterministic routing rules, and static page serving. `backend/main.py` must expose `app` for the runbook's Uvicorn command.
- `backend/store.py` and local SQLite setup for synthetic clients, accounts, cases, and assignments. Import `contracts/demo_fixture_v1.json` immediately; Agent 4 may later add richer `data/` files without changing the fixed IDs.
- `backend/reset_demo.py`, `requirements.txt`, `README.md`, and `tests/backend/`: synthetic-data reset, app dependencies, run instructions, and meaningful API tests. `python -m backend.reset_demo` must restore the fixture state. Include Agent 1's `requirements-aws.txt` in the app install path.
- No ownership of `contracts/API_V1.md`; it is frozen. Propose a version-two contract to the team if needed.

Do not edit `backend/aws/` (Agent 1), `frontend/client/` (Agent 3), `frontend/staff/` or `data/` (Agent 4). Serve those paths even if their files are still being built.

## Frozen HTTP contract

Implement the exact paths and field names in `contracts/API_V1.md`:

```text
POST /intake/start
POST /intake/{session_id}/turn
POST /intake/{session_id}/confirm
GET  /staff/cases
GET  /staff/cases/{case_id}
GET  /staff/cases/{case_id}/candidates
POST /staff/cases/{case_id}/assign
```

Serve `/client` and `/staff` from the separate frontend directories on the same origin, port 8000. Agents 3 and 4 already have `contracts/mock_api.py` for independent work. Use a temporary local AI stub behind your real API until Agent 1's Bedrock adapter is ready; keep its response shape identical to version one.

Agent 1 exposes `intake_turn(client_id, transcript, selected_option_id, tools) -> dict` and `triage_case(confirmed_request, tools) -> dict`. Supply the authorized tool callbacks. Validate the returned dictionaries against the case schema; the model is not a source of account facts. Account balances, types, and history come only from Agent 4's synthetic records with source IDs and as-of dates.

## Deterministic rules you own

- `client_id` must come from the active synthetic demo session; the client cannot request another client's account IDs. The visible role switcher is **simulated access control**, not production authentication. Staff endpoints require the staff demo role.
- A model suggestion is a proposal. Do not mark an account as selected or an amount as confirmed until the client explicitly chooses or edits it on the review screen.
- A confirmed case retains the original words, client-approved wording, selected account or unresolved marker, staff summary, categories, flags, and source references.
- If the case indicates possible fraud, unauthorized access, or account takeover, recommend the specialist review queue rather than a general advisor. Staff still makes the final decision.
- Rank advisor candidates using the fictional directory: existing relationship when applicable, specialty match, availability, meeting preference, and capacity. Do not let the model invent licensing or state eligibility.
- A model or AWS error preserves the draft and returns a useful message. `assign` records the staff member's selected advisor and reason. No outbound message, transaction, appointment, or real LPL system call occurs.

## Build order and definition of done

1. Implement endpoints against `contracts/demo_fixture_v1.json` and the frozen contract. Do not wait for Agent 4's expanded data or Agent 1's adapter.
2. Load the fixture into local SQLite or a simple local repository. Avoid requiring DynamoDB for the first integrated demo.
3. Implement intake state and confirmation, then triage and staff queue, then candidate ranking and assignment.
4. Swap endpoint stubs for Agent 1's live Bedrock adapter. Keep an explicit mock mode for offline UI development, but the final judged path must use Bedrock.
5. Run a full synthetic end-to-end test for ambiguous IRA, clear request, and specialist security routing. Record one-command startup and demo reset in `README.md`.

Done means a client request submitted through the API appears in the staff queue, displays supported account facts, and can be manually assigned. The core path must work with typed input and live Bedrock. The exact launch and reset commands in `INTEGRATION_RUNBOOK.md` must work from a clean checkout.

## Synchronization with the other agents

`contracts/API_V1.md` is the frozen source of truth. Implement it without waiting for other agents. If a field is insufficient, propose a version-two change and seek team agreement; do not silently alter version one. Push your branch and open a pull request; do not push directly to `main`. Send the team your branch/commit, endpoint status, and blockers at each milestone. Pull merged `main` before the final integration run.
