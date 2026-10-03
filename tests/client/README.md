# Agent 3 client handoff

Branch: `codex/agent3-client-ui`. Owned implementation: `frontend/client/`.

The vanilla HTML/CSS/JS client implements typed intake, debounced and serialized turns, at most three suggestions, one clarification question, glossary explanations, account rejection, human-help requests, editable review, explicit confirmation, and a returned case ID. Optional microphone input uses browser speech recognition, **not AWS Transcribe**. Unsupported browsers and denied permissions retain the complete typing flow.

## Run the standalone development preview

From the repository root:

```sh
python3 tests/client/preview.py
```

Open <http://127.0.0.1:8003/client>. The helper starts the unchanged frozen mock on port 8001 and serves the client on port 8003. Both bind to loopback. If either port is in use, choose others with `--port 8003 --api-port 18011`.

The preview is visibly labeled as preset fictional responses with no live AI. It is for development and backup screenshots, not the judged AI demonstration.

## Integrate with Agent 2

Serve `frontend/client/index.html` at `/client` or `/client/`, and serve `app.js` and `style.css` below `/client/`. The production page calls same-origin endpoints by default. To use a separately running API, set `window.SAMEPAGE_API_BASE` before `app.js` loads. `window.SAMEPAGE_MOCK_MODE = true` enables the development notice; the preview helper sets both without changing production files.

Requests follow `contracts/API_V1.md`, including `X-Demo-Role: client`, the selected `X-Demo-Client-Id`, full edited text, `text`/`voice` input mode, returned suggestion IDs, and nullable account/amount on confirmation. Turns are debounced 1.25 seconds and serialized with a minimum 1.2-second interval; confirmation also respects the last turn's interval. Backend pacing must still coordinate different clients and staff calls.

No contract or fixture files changed. Version one has no client-profile read endpoint, so `app.js` contains only the frozen two clients' names, account labels, IDs, and masks. No balances, events, or staff records are embedded. The backend remains responsible for authorization. Additional demo clients or accounts need an agreed profile contract or a coordinated update to this projection.

The API has no draft-summary field. The review uses the client's words, or a short withdrawal-discussion template with their selected account when that is the returned intent. The client can edit this wording. Amounts start blank and are only sent after explicit entry and final confirmation. “None of these” and “Talk to a person” send a null account if the client leaves it unresolved. V1 cannot explicitly clear a prior account selection during a turn; the UI ignores a stale server selection and sends the client's final selection in `/confirm`.

The API has no confirmation idempotency or receipt-lookup endpoint. A lost/uncertain confirmation response blocks repeated submission and asks demo staff to check the queue. Definite 4xx rejections allow correction and retry. Local storage saves only the draft client and words; refresh never starts an API call or submits a case automatically. Review edits remain intact when returning to the same unchanged request within a session.

## Run browser checks

Node.js, Python 3, and a Playwright Chromium install are needed:

```sh
cd tests/client
npm ci
npx playwright install chromium
npm test
```

The suite owns isolated ports 18001 and 18003 and shuts down its server after testing. It checks keyboard completion of the scripted Roth/rollover mismatch, returned staff-case values, a plain request, manual amount validation and null handling, refresh behavior, debounce/stale-response handling, account rejection, recoverable errors, uncertain confirmation, microphone fallback, and a 390px mobile layout. `artifacts/` holds fresh screenshots and is ignored by Git.

## Under-two-minute demo

1. Choose Mara Ellis and start a request.
2. Type “I need six thousand dollars from the Roth thing from my old job.”
3. Show the clarification and open “What is a rollover IRA?”
4. Choose “Retirement account from former employer” and review.
5. Edit the wording to “I want to discuss using $6,000 from my retirement account from my former employer for care expenses.” Enter `6,000` in the amount field.
6. Select **Confirm and send request**. Give the returned case ID to the staff-view presenter.

`demo-backup/` contains mock-backed screenshots; recapture these against the integrated Bedrock app before the final demo. Integration with the real backend, live Bedrock, and actual microphone hardware still needs the joint rehearsal described in `INTEGRATION_RUNBOOK.md`.
