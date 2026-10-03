# Final Agent Integration and App Verification

You are the final integration agent for SamePage. Start this task **after Agents 1 through 4 have finished their branches or opened ready pull requests**. Work from a separate clone or worktree of [Da0t/LPL-Hackathon](https://github.com/Da0t/LPL-Hackathon) on branch `codex/final-integration`. Read `HACKATHON_PROJECT_BRIEF.md`, `SAMEPAGE_PRODUCT_SPEC.md`, `contracts/API_V1.md`, and `INTEGRATION_RUNBOOK.md` before changing code.

Your job is to combine the four pieces, launch the **real application**, exercise the full client-to-staff flow, fix integration defects, and report what actually works. Do not count `contracts/mock_api.py` or canned AI responses as a successful final demo.

## Step 1 Confirm all four pieces are present

Check that the integration branch contains:

- Agent 1: `backend/aws/bedrock_agent.py` and `AWS_SETUP.md`.
- Agent 2: `backend/main.py` exposing a FastAPI object named `app`, real API routes, storage, and `backend/reset_demo.py`.
- Agent 3: the client page under `frontend/client/`.
- Agent 4: the staff page under `frontend/staff/` and fictional records under `data/`.

If ready PRs are not yet on `main`, review and integrate them into your branch without overwriting another agent's work. Resolve conflicts against the frozen contract in `contracts/API_V1.md`. If an agent's branch is still unfinished, report the exact missing part and continue with integration work that is possible. Open a PR from your integration branch when it is ready; do not silently force-push `main`.

## Step 2 Install and configure

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Use Agent 1's `AWS_SETUP.md` to access the event account. Set `AWS_REGION=us-east-1`, `BEDROCK_MODEL_ID` to an **actually available model ID whose model name is on the hackathon allowlist**, and `SAMEPAGE_AI_MODE=bedrock`. Never paste credentials into code, logs, screenshots, or the repository. If setup or dependencies fail, fix the relevant code or documentation and retry.

## Step 3 Run the final application

Run this exact command from the repository root:

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Confirm both pages load:

- `http://127.0.0.1:8000/client`
- `http://127.0.0.1:8000/staff`

The command is expected to become runnable only after Agent 2's code exists. If it raises an import, configuration, or startup error, trace and fix that error, then rerun. Do not replace the command with the mock server to claim completion.

## Step 4 Prove the complete workflow

Use only synthetic data. Reset the demo with `python -m backend.reset_demo` if that command is available; if it is missing, implement it or document a safe equivalent for local fictional data. Then:

1. Open `/client` as `CLIENT-017`. Type or speak: “I need six thousand dollars from the Roth thing from my old job.”
2. Confirm the live Bedrock agent sees no Roth IRA in that client's records, asks a clarifying question, and offers the rollover IRA without silently choosing it. Verify that the agent really makes a Bedrock call through Agent 1's adapter.
3. Select the rollover IRA, edit or confirm the plain-language summary, and submit. Record the new case ID.
4. Open `/staff`. Find **the same case ID**. Check original words, confirmed request, category tags, masked account, balance with as-of date, relevant prior event with source ID, unresolved questions, and advisor reasons.
5. Assign the case to the fictional matching advisor and confirm the status changes to `assigned`.
6. Open `CASE-SEC-1` and check that it is marked for specialist review, not automatically routed to an ordinary advisor.
7. Test the typed path even if voice works. Test one error path, such as denied microphone permission or a model failure, and confirm the client's draft is not lost.

Record the commands run, the case ID, and the result of each check. A working mock or screenshots alone are not proof that the real path works.

## Step 5 Finish the handoff

Fix integration defects within scope, then rerun the complete workflow from a clean start. Update `README.md` and `INTEGRATION_RUNBOOK.md` if the actual setup differs from the planned commands. State clearly which voice path works: AWS Transcribe, browser speech recognition, push-to-talk, or typed input only. Confirm the chosen AWS model and region without exposing account credentials.

Open a PR with your integration fixes and a concise report: launch command, live Bedrock evidence, end-to-end result, remaining failures, and the exact demo reset steps. Tell the team if a required hackathon deliverable remains unfinished. The goal is a repeatable live demo, not merely a successful server startup.
