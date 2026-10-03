# Coherent AWS setup: Bedrock

> **Status:** this covers Amazon Bedrock, the Guardrail, and Transcribe. Cognito and DynamoDB for the client portal are provisioned separately; see "Run it" in [`README.md`](README.md). Internal names still read `samepage` (for example `SAMEPAGE_AI_MODE`), and "Agent 1" refers to the branch that built this adapter.

This covers the AWS side of Coherent: the Bedrock intake + triage adapter, its
configuration, least-privilege IAM, the optional Guardrail, optional Transcribe,
and the live smoke test. The judged path is **live Bedrock** with real
tool use. The typed client flow must work before voice is attempted.

## 1. What runs

| Piece | Status | File |
| --- | --- | --- |
| Bedrock intake + triage adapter (Converse API, native tool use) | **Required, runs** | `backend/aws/bedrock_agent.py` |
| Region/model/config from env (no creds in code) | **Required, runs** | `backend/aws/config.py` |
| Bedrock Guardrails (blocks investment/tax advice, masks PII) | **Optional, recommended** | `infra/guardrail.json` |
| Least-privilege IAM policy | **Required to deploy** | `infra/iam_policy.json` |
| Amazon Transcribe streaming (voice) + financial custom vocabulary | **Built, vocabulary live** | `backend/aws/transcribe.py` |

### Voice: Transcribe financial custom vocabulary

Two layers give better speech handling:

1. **Understanding (always on):** the intake agent normalizes shorthand, acronyms,
   phonetic fragments, and loosely named documents to approved glossary terms
   ("R O I" → return on investment, "the tax form" → 1099-R) via
   `Store.suggest_terms` and the `suggest_financial_terms` tool. Works for typed
   input and any speech source.
2. **Hearing (Amazon Transcribe):** a custom vocabulary biases speech-to-text
   toward financial terms. Create/refresh it (boto3 only, no S3):

   ```bash
   AWS_PROFILE=lpl-hackathon python -m backend.aws.transcribe   # -> state: READY
   ```

   Then `transcribe_pcm_chunks(...)` / `transcribe_wav(path)` use it automatically.
   Vocabulary name: `samepage-financial-terms` (override with `TRANSCRIBE_VOCAB_NAME`).
   The client request editor uses browser speech recognition, labeled as a browser
   feature. The Transcribe path is built and its vocabulary is live, but no page
   calls it yet; do not describe the demo's voice input as Amazon Transcribe.

## 2. Configuration (environment only)

```bash
export AWS_REGION=us-east-1                 # hackathon requirement
export BEDROCK_MODEL_ID=<verified model id> # see step 3
export SAMEPAGE_AI_MODE=bedrock             # "stub" = offline dev only, never judged
# optional:
export BEDROCK_GUARDRAIL_ID=<id>
export BEDROCK_GUARDRAIL_VERSION=<version>
export BEDROCK_MIN_INTERVAL_SECONDS=1.0     # ~1 Bedrock call/sec pacing
export BEDROCK_MAX_TOKENS=1024
export BEDROCK_TEMPERATURE=0.2
```

**No access keys live in the repo or code.** boto3 resolves credentials from the
event account's supported mechanism (SSO / assumed role / profile). Do not commit
`.env`, credentials, or event-account IDs.

## 3. Verify the model is actually enabled (do this first)

A name on the hackathon allowlist does not guarantee an enabled model ID in the
event account. In `us-east-1`, confirm access, then pick a **tool-capable**
model (Converse tool use is supported by Claude, Amazon Nova, and Llama; it is
required by this adapter):

```bash
# List models whose access is granted in this account/region:
aws bedrock list-foundation-models --region us-east-1 \
  --query "modelSummaries[].modelId" --output text

# If the model requires a cross-region inference profile, list those too:
aws bedrock list-inference-profiles --region us-east-1 \
  --query "inferenceProfileSummaries[].inferenceProfileId" --output text
```

Right-sizing guidance: use a fast, cheap model for intake (e.g. a Nova Lite or
Haiku-class model on the allowlist) and the same or a slightly stronger model for
triage. Set the chosen ID as `BEDROCK_MODEL_ID` and tell the team the **model
name and ID** (never credentials).

**Verified choice:** `BEDROCK_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0`
(Claude Haiku 4.5, via its US inference profile). Confirmed enabled in the event
account and passing the live smoke test below. Haiku 4.5 is fast, cheap, and
strong at tool use, so it is a good fit for both intake and triage. Nova Lite
(`us.amazon.nova-2-lite-v1:0`) is a drop-in alternative if ever needed.

## 4. Least-privilege IAM

Use `infra/iam_policy.json`. Replace `ACCOUNT_ID`, the model ID / inference
profile ID, and the optional guardrail ID. It grants only `bedrock:InvokeModel`
(+ stream) on the single model, optional `bedrock:ApplyGuardrail`, and optional
`transcribe:StartStreamTranscription`. No wildcards on the model resource.

## 5. Optional Guardrail (recommended, strong "Best Use of AWS" story)

The product promise is that the assistant never gives investment/tax advice and
never invents facts. A Guardrail enforces the first part at the platform level.

```bash
aws bedrock create-guardrail --region us-east-1 \
  --cli-input-json file://infra/guardrail.json
# Note the returned guardrailId, then publish a version:
aws bedrock create-guardrail-version --region us-east-1 \
  --guardrail-identifier <guardrailId>
# Export BEDROCK_GUARDRAIL_ID / BEDROCK_GUARDRAIL_VERSION to turn it on.
```

When set, every Converse call includes `guardrailConfig`; a blocked turn raises
`GUARDRAIL_BLOCKED`, which the backend turns into a "talk to a person" response.

## 6. Live smoke test (the command to record and rerun)

From the repo root, with credentials exported:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-aws.txt
export AWS_REGION=us-east-1
export BEDROCK_MODEL_ID=<verified model id>
export SAMEPAGE_AI_MODE=bedrock
python -m tests.aws.smoke_live
```

Expected: intake notices there is no Roth IRA for CLIENT-017 and asks about the
rollover IRA; triage of the sign-in case returns `fraud_or_security` and
`routing_hint: security_specialist_review`. Prints `SMOKE RESULT: PASS`.

**Status: verified PASS** against the event account with
`us.anthropic.claude-haiku-4-5-20251001-v1:0`. Credentials come from the Workshop
Studio participant role under AWS profile `lpl-hackathon` (temporary; re-paste
when they expire). Exact command used:

```bash
AWS_PROFILE=lpl-hackathon AWS_REGION=us-east-1 \
  BEDROCK_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0 \
  SAMEPAGE_AI_MODE=bedrock python3 -m tests.aws.smoke_live
```

## 7. Offline unit tests (no credentials needed)

```bash
pip install -r requirements-aws.txt pytest
python -m pytest tests/aws -q
```

These drive the real tool-use loop with a scripted fake Bedrock client and
fixture-backed tool callbacks, covering: the Roth mismatch, dropping invented
accounts, feeding tool results back to the model, guardrail blocking, taxonomy
validation, and the fraud-routing safety net.

## 8. The seam to Agent 2 (backend)

Agent 2 imports and calls:

```python
from backend.aws import intake_turn, triage_case, BedrockAdapterError
```

```python
intake_turn(client_id, transcript, selected_option_id, tools) -> dict
triage_case(confirmed_request, tools) -> dict
```

`tools` is an object (or dict) providing authorized callbacks. The adapter
**injects the authorized client/account id itself** and never passes model-chosen
identifiers to these callbacks:

| Callback | Signature |
| --- | --- |
| `get_relevant_accounts` | `(client_id: str, phrase: str) -> list[{account_id, account_type, familiar_label, masked_identifier?}]` |
| `get_approved_definition` | `(term: str) -> {term, plain} | None` |
| `get_relevant_account_history` | `(account_id: str) -> list[{type, date, source_id, summary?}]` |
| `search_advisor_directory` | `(categories: list[str], preferences: dict) -> list[{advisor_id, display_name, specialties, available}]` |

`intake_turn` returns `{suggestions (<=3), question, definitions, candidate_intent,
selected_account_id, uncertainty}`; the backend adds `session_id`, echoes
`transcript`, and sets `status`. Suggestions that do not map to a real account for
the client are dropped, so the model cannot surface an invented account.

`triage_case` returns `{client_summary, staff_summary, intent, categories,
unresolved_questions, flags, recommended_advisor_ids, routing_hint}`. Categories
are validated against the frozen taxonomy; a `fraud_or_security` case is forced to
`routing_hint: security_specialist_review` with no advisor recommendations. The
backend makes the final deterministic routing decision and attaches verified
account facts.

**Errors:** hard failures raise `BedrockAdapterError(code, message)`. The backend
should catch it, keep the draft, set `status: needs_clarification`, show
`message`, and offer typing or a person (per `contracts/API_V1.md`). Transient
throttling/timeouts are retried with bounded backoff before that point.

**Dependency note for Agent 2:** include `requirements-aws.txt` from the app
`requirements.txt`. If a contract or dependency change is needed, propose a
version-two change to the team rather than editing version one.
