# Agent 3 Client Experience

You are one of four parallel development agents building SamePage for the LPL hackathon. **You own the client-facing page and its interaction design.** Work in your own clone or worktree of [Da0t/LPL-Hackathon](https://github.com/Da0t/LPL-Hackathon) on branch `codex/agent3-client-ui`. First read `HACKATHON_PROJECT_BRIEF.md` and `SAMEPAGE_PRODUCT_SPEC.md`, especially the client journey and version-one API contract. Agent 1 owns AWS, Agent 2 owns the backend, and Agent 4 owns staff UI and synthetic data.

## Your mission

Make the first half of the five-minute demo feel polished and human: a client describes a need in ordinary words, sees a small number of grounded suggestions, gets a simple explanation, clarifies a mismatch, and confirms the request. The page must be usable with typing even if microphone permissions or speech services fail.

## Files you own

- `frontend/client/index.html`, `frontend/client/app.js`, and `frontend/client/style.css`.
- Optional browser-only helper code within `frontend/client/`, including prototype microphone capture.
- Focused browser/UI checks under `tests/client/` if needed.

Do not edit backend endpoints, `backend/aws/`, staff UI, or seed data. Ask Agent 2 for API changes and Agent 4 for fixture changes. Avoid a React build or large design framework; Agent 2 will serve this page from FastAPI at `/client`.

## Required client flow

1. Choose the fictional demo client and start a session with `POST /intake/start`.
2. Show an editable transcript/text field. As a complete phrase is entered, send a debounced `POST /intake/{session_id}/turn`. Do not call on every keystroke; avoid flooding Bedrock and respect the roughly one-call-per-second event limit.
3. Show at most three large suggestion cards, plus **None of these** and **Talk to a person**. The user can select a card, continue speaking/typing, or correct the transcript.
4. Show one clarifying question at a time. A term explanation is short and readable; “rollover IRA” must be explainable without assuming the client knows tax vocabulary.
5. On the final review, separate **What you said** from **What we understood**. Show the selected account's familiar label and masked ID, not a full account dump. Let the client edit the summary, selected account, and stated amount. Require a final **Confirm and send request** action.
6. Display the returned case ID and a truthful next step. No screen should imply a withdrawal, appointment, or advisor assignment already occurred.

## Microphone behavior

The hackathon prototype may use the browser's speech-recognition capability for interim text; Agent 1 owns any AWS Transcribe work. Keep the UI label honest about which path runs. If browser speech is unsupported or permission is denied, immediately offer typing with the same features. If Agent 1 delivers Transcribe Streaming in time, coordinate an adapter with them rather than rewriting the intake UI.

For the scripted demo, use only fictional names, accounts, and spoken content. The key moment is: the client says “the Roth thing from my old job,” the synthetic profile has no Roth IRA, and the interface displays the agent's clarifying question instead of pretending it found a Roth account.

## Accessibility and presentation quality

Use large readable type, clear contrast, keyboard-operable controls, visible focus, and an obvious pause/stop control. Do not overwhelm the client with a long list of financial terms. Show loading and recoverable error states without erasing their words. The page should fit on a laptop projector at normal zoom. The interaction should take under two minutes in the final presentation.

## Build order and definition of done

1. Build the screen against Agent 2's stub responses or local JSON examples from the product spec.
2. Implement text intake, suggestions, clarification, final review, and submit. Verify a corrected client request reaches the backend.
3. Add microphone input and fallback only after typing works.
4. Test the scripted IRA mismatch and a plain non-ambiguous request. Check that refreshing a draft does not silently send it.

Done means the client can finish the core request end to end, including explicit confirmation, using only the keyboard if necessary. Capture a short recording or screenshots for the demo backup after integration.

## Synchronization with the other agents

The version-one API contract in `SAMEPAGE_PRODUCT_SPEC.md` is your source of truth. At the first check-in, obtain Agent 2's stub endpoint URL and example responses. Send the team your branch/commit, working screens, fields you consume, and blockers at each milestone. Push your branch and open a pull request; do not push directly to `main`. If the backend response differs from the spec, request a contract decision from Agent 2 rather than silently changing field names. Pull merged `main` and retest before final demo rehearsal.
