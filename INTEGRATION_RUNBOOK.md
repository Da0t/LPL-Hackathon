# SamePage Integration and Run Guide

This is the agreed final launch path **after all four development branches have been merged**. The application entry point does not exist yet; Agent 2 is assigned to create `backend/main.py` with a FastAPI object named `app`. The [mock API](contracts/mock_api.py) is only a development aid and is not the final application.

## What the four agents deliver

| Agent | Required part |
| --- | --- |
| 1 AWS | `backend/aws/bedrock_agent.py`, model/config setup, and a live Bedrock smoke test |
| 2 backend | `backend/main.py:app`, API routes, case storage, and demo reset command |
| 3 client UI | `frontend/client/`, served by the backend at `/client` |
| 4 staff and data | `frontend/staff/` and synthetic `data/`, served at `/staff` |

The teammate acting as integrator merges each agent's pull request into `main`, checks for file conflicts, and runs the full application from a **fresh clone or clean checkout**. Agents should not all work in one shared directory.

## Final application launch

From the repository root, after all four PRs are merged:

```bash
git pull origin main
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Follow Agent 1's `AWS_SETUP.md` to use the event account's credential flow. Do not put access keys in the repository. Agent 1 and Agent 2 must implement these environment variables:

```text
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=<verified allowlisted model ID from the event account>
SAMEPAGE_AI_MODE=bedrock
```

Then run the **final app**:

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/client` for the client screen and `http://127.0.0.1:8000/staff` for the staff screen. The FastAPI API is on the same origin. Agent 2 must ensure `requirements.txt` installs FastAPI, Uvicorn, and Agent 1's AWS dependencies.

If you want to work on a screen **before** the final backend exists, run `python3 contracts/mock_api.py` on port 8001 and point the screen's `window.SAMEPAGE_API_BASE` at `http://127.0.0.1:8001`. This mock returns preset fictional answers and must not be presented as the final AI demo.

## Integration acceptance check

1. Start the app with `SAMEPAGE_AI_MODE=bedrock`. Verify Agent 1's live Bedrock adapter is actually called; a canned mock response does not satisfy the hackathon's working-agent goal.
2. On `/client`, choose fictional client `CLIENT-017`. Type or speak “I need six thousand dollars from the Roth thing from my old job.” Confirm the agent identifies uncertainty because the fixture has no Roth IRA for that client.
3. Select the rollover IRA and confirm the final request. Record the returned case ID.
4. On `/staff`, find **that same case ID**. Check that the original words, confirmed request, masked account, balance as-of date, prior rollover source, categories, and unresolved questions appear.
5. Check that advisor candidate `ADV-03` has a visible reason. Assign the case as staff and confirm the status becomes `assigned`.
6. Open the fictional security case `CASE-SEC-1`. It must point to specialist review, not automatically assign a general advisor.
7. Repeat once with typing if microphone input fails. The typed flow must work completely. If voice uses browser recognition or is not complete, describe that accurately in the presentation.

Agent 2 must implement `python -m backend.reset_demo` to restore local synthetic data and clear new cases and assignments. Run it before each judged rehearsal and document whether the server must restart. Never reset or delete real client data; the prototype contains only fictional records.

## If the integrated app fails

- **Bedrock denied:** Check `AWS_REGION`, model access, the verified model ID, and event-account credentials. Agent 1 owns the fix.
- **A page cannot call the API:** Compare the request and response with `contracts/API_V1.md`. Agent 2 owns the real endpoint; Agents 3 and 4 own their page calls.
- **Account or advisor IDs differ:** Preserve the fixed IDs in `contracts/demo_fixture_v1.json`. Agent 4 owns expanded data; Agent 2 owns import and validation.
- **Voice fails:** Continue through the typed path. Do not switch the judged AI path to the preset mock.

The integrator should update this guide if an implementation detail changes, then tell all four teammates. The final deck and code ZIP remain separate hackathon deliverables due by the time in `HACKATHON_PROJECT_BRIEF.md`.
