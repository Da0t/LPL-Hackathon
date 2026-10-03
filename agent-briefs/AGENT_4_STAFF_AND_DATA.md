# Agent 4 Staff Dashboard and Synthetic Data

You are one of four parallel development agents building SamePage for the LPL hackathon. **You own the staff-facing page, the fictional account/advisor data, and the demo narrative.** Work in your own clone or worktree of [Da0t/LPL-Hackathon](https://github.com/Da0t/LPL-Hackathon) on branch `codex/agent4-staff-data`. First read `HACKATHON_PROJECT_BRIEF.md` and `SAMEPAGE_PRODUCT_SPEC.md`, especially the case document, staff routing, and version-one API contract. Agent 1 owns AWS, Agent 2 owns the backend, and Agent 3 owns client UI.

## Your mission

Make the second half of the demo show the business value: the client request arrives already clarified and categorized; staff can see the client's own words, relevant account facts, any uncertainty, and suitable fictional advisors; a human chooses the assignment. Provide the synthetic records that make the whole flow possible.

## Files you own

- `data/clients.json`, `data/accounts.json`, `data/events.json`, `data/advisors.json`, and `data/glossary.json`.
- `frontend/staff/index.html`, `frontend/staff/app.js`, and `frontend/staff/style.css`.
- `DEMO_SCRIPT.md` with the exact fictional scenario and reset steps.

Do not edit Agent 2's backend, Agent 1's AWS code, or Agent 3's client page. Keep data fields stable after your first published fixture. Ask Agent 2 before changing IDs or schemas that their API imports.

## Seed data to publish first

Make three entirely fictional clients, six to eight accounts, relevant dated events, eight fictional advisors, and ten approved plain-language glossary entries. Use coherent IDs and source references. Each account needs an owner client ID, account type, familiar label, masked identifier, balance snapshot, and `balance_as_of`. Each event needs account ID, type, date, and source ID. Each advisor needs specialty tags, active/available status, meeting mode, capacity, and whether they are the client's existing advisor. Never use a real LPL advisor or real client data.

The critical client is `CLIENT-017`: they say “Roth thing from my old job,” but their records contain a **rollover IRA** from a former employer and **no Roth IRA**. Include a fictional balance and a prior rollover event so page 2 of the staff case can show why that account is relevant. Add a clear Roth IRA question for another client, a beneficiary request, and a possible unauthorized-access scenario that should be flagged for a specialist queue. Do not embed a hard-coded final answer in the client data; the live model must interpret the request.

Send the five data files or their committed branch to Agent 2 as soon as they are valid. Agent 2 needs them to implement storage and authorized lookup tools; do not wait for your UI to be complete.

## Staff dashboard behavior

- Display a queue with case ID, time, client, confirmed plain-language request, categories, status, and flags. Filters can be simple.
- Clicking a case opens the two-page equivalent in the spec: original words and confirmed summary first; only relevant account context, masked ID, balance as-of date, and prior event on the second section. Make source labels visible.
- Show at most three advisor candidates with specialty, availability, existing-client relationship, and an understandable reason. The staff member can select or override and must enter a reason before `POST /staff/cases/{case_id}/assign`.
- If a security flag is present, show the specialist review destination prominently rather than a standard advisor match.
- Show assigned status only after a successful API response. Handle an empty queue and API error cleanly.

Use Agent 2's `GET /staff/cases`, `GET /staff/cases/{case_id}`, `GET /staff/cases/{case_id}/candidates`, and `POST /staff/cases/{case_id}/assign` exactly as written in the product spec. Agent 2 will serve your page at `/staff`.

## Demo narrative and definition of done

Write a five-minute script that gives the client-side demo roughly two minutes, the staff-side demo roughly one minute, and leaves time for the problem, LPL acquisition thesis, AWS architecture, and measurable impact. The “wow” moment is a mismatch caught before an advisor receives a misleading request. Show the same client request flowing into staff view without re-entering it. Use the LPL PowerPoint template later for the deck; your script is not a substitute for the required presentation.

Done means a submitted case appears in the queue, the staff member can read its evidence and account context, and a manual assignment changes its status. Your data and UI should also support the specialist-routing case. Provide screenshots or a short recording as a backup after integration.

## Synchronization with the other agents

The version-one contract in `SAMEPAGE_PRODUCT_SPEC.md` is the shared source of truth. Publish fixture IDs and field names to Agent 2 early; Agent 3 needs the fictional client label and demo scenario. Send the team your branch/commit, fixture changes, working screens, and blockers at each milestone. Push your branch and open a pull request; do not push directly to `main`. If you need a new field, ask Agent 2 to update the shared contract and notify everyone before relying on it. Pull merged `main` and rehearse the complete flow before judging.
