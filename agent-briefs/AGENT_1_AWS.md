# Agent 1 AWS and Model Integration

You are one of four parallel development agents building SamePage for the LPL hackathon. **You own all AWS work.** Work in your own clone or worktree of [Da0t/LPL-Hackathon](https://github.com/Da0t/LPL-Hackathon) on branch `codex/agent1-aws`. First read `HACKATHON_PROJECT_BRIEF.md` and `SAMEPAGE_PRODUCT_SPEC.md`, especially the AWS and API contract sections. Your teammates own the backend API, client UI, and staff UI. Do not build their screens or change the shared API without agreement.

## Your mission

Provide a real Amazon Bedrock powered intake and triage adapter so the app can interpret a client's everyday language, ask a grounded clarifying question, explain terms from approved definitions, and produce structured fields after client confirmation. Your first deliverable is a working Bedrock call in `us-east-1`. Speech integration comes **after** the typed end-to-end flow works.

## Files you own

- `backend/aws/bedrock_agent.py`: Bedrock model calls, prompts, tool-use loop, parsing, timeout/retry, and rate pacing.
- `backend/aws/config.py`: region and model configuration from environment variables; no credentials in code.
- `backend/aws/transcribe.py`: optional Amazon Transcribe integration once Bedrock works.
- `infra/` and `AWS_SETUP.md`: only the infrastructure/configuration needed to reproduce the demo.
- `requirements-aws.txt`: AWS-specific dependencies for Agent 2 to include from the app requirements.

You may add focused tests under `tests/aws/`. Agent 2 owns `backend/main.py`, HTTP endpoints, schemas, storage, and the top-level `requirements.txt`. Tell Agent 2 if you need a dependency or contract change.

## Frozen interface to Agent 2

Export these Python functions or methods, synchronously or asynchronously as agreed with Agent 2 in the first check-in:

```python
intake_turn(client_id: str, transcript: str, selected_option_id: str | None, tools) -> dict
triage_case(confirmed_request: dict, tools) -> dict
```

Agent 2 supplies authorized `tools` callbacks. Expected callbacks are `get_relevant_accounts`, `get_approved_definition`, `get_relevant_account_history`, and `search_advisor_directory`. Your adapter must **not** query files or a database directly. This keeps account access and role checks in Agent 2's service layer.

`intake_turn` returns at most three suggestion objects `{id, label, account_id?}`, one `question` or null, `definitions` as `{term, plain}`, `candidate_intent`, `selected_account_id` or null, and `uncertainty` or null. `triage_case` returns a plain-language client summary, a staff summary, categories from the fixed taxonomy in the spec, unresolved questions, and flags. Do not invent an account, balance, transaction history, or amount. Missing data stays missing. Keep the client's original words available to Agent 2.

## AWS rules you must satisfy

- Work in `us-east-1`. Verify the chosen **actual Bedrock model ID** is available in the event account and its model name appears in the brief's allowlist. Use one right-sized generation model; do not use another model for embeddings or reranking unless separately allowed and necessary.
- Use IAM or the event account credential flow, never hard-coded access keys. Create a minimal policy for the chosen model and optional Transcribe actions. Do not commit `.env`, credentials, transcripts from real people, or account IDs from the event account.
- Pace Bedrock calls around the brief's approximate one-call-per-second limit. Give errors a stable response that lets the client keep typing or request human help. Log request IDs and error categories without logging sensitive case content.
- Use Bedrock for an actual tool-using agent. Give it narrow tool specifications and let deterministic code validate its output. A hard-coded response for the demo scenario does not count as the working agent.
- If you use S3 for Transcribe or exports, keep every bucket private. Prefer no S3 for the core flow.

## Build order and definition of done

1. Confirm region, model access, and one successful generation call. Tell the team the chosen **model name and ID**; do not share credentials.
2. Implement `intake_turn` against fake tool callbacks and the synthetic “Roth thing from my old job” scenario. It should notice that the synthetic account list contains no Roth IRA and ask a question instead of claiming a match.
3. Implement `triage_case` with schema-constrained output and a second scenario. The downstream backend makes the final routing decision.
4. Add bounded retries, pacing, and a failure path. Run one live smoke test with synthetic data and record the exact command in `AWS_SETUP.md`.
5. Only then attempt Transcribe Streaming. If it is incomplete, leave the typed flow intact and state clearly that microphone transcription is a browser/demo feature or pending.

Done means Agent 2 can import your adapter and run the core request through live Bedrock without changing the HTTP contract. Include a brief note of which AWS pieces actually run, which are optional, and the commands another teammate needs to reproduce them.

## Synchronization with the other agents

The version-one contract in `SAMEPAGE_PRODUCT_SPEC.md` is the shared source of truth. At the first check-in, confirm your Python signatures with Agent 2. Push your branch and open a pull request; do not push directly to `main`. At each milestone, send the team your branch/commit, what works, any interface change proposed, and any blocker. If a contract change is needed, wait for Agent 2 to update the shared contract and for Agents 3 and 4 to acknowledge it before relying on the change. Pull merged `main` before final integration.
