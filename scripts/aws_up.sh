#!/usr/bin/env bash
# =============================================================================
# aws_up.sh — one command that stands up EVERY AWS piece of Coherent, in order.
#
# This is a thin, annotated orchestrator over the real provisioning/deploy code
# that already lives in this repo. It documents, in dependency order, exactly
# which AWS service each step creates and which file implements it. Every step
# is idempotent/resumable: re-running picks up where it left off.
#
# Run from the repo root with authorized AWS credentials for the event account:
#
#     AWS_PROFILE=lpl-hackathon ./scripts/aws_up.sh            # provision only
#     AWS_PROFILE=lpl-hackathon ./scripts/aws_up.sh --deploy   # + host on EC2/CloudFront
#     AWS_PROFILE=lpl-hackathon ./scripts/aws_up.sh --local    # provision, then run locally
#
# Nothing here hard-codes credentials or account IDs; boto3 resolves creds from
# the profile/role/SSO in your environment. Region is pinned to us-east-1.
# =============================================================================
set -euo pipefail

cd "$(dirname "$0")/.."            # repo root
export PYTHONPATH=.               # so `backend.*` imports resolve in every script
PY="${PYTHON:-python3}"

# ---- Shared configuration (environment only; see backend/aws/config.py) -----
export AWS_REGION="${AWS_REGION:-us-east-1}"            # hackathon requirement
export AWS_DEFAULT_REGION="$AWS_REGION"
# Tool-capable Bedrock model, as an inference profile enabled in the account:
export BEDROCK_MODEL_ID="${BEDROCK_MODEL_ID:-us.anthropic.claude-haiku-4-5-20251001-v1:0}"
export SAMEPAGE_AI_MODE="${SAMEPAGE_AI_MODE:-bedrock}"  # "stub" = offline, never judged

banner() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

# -----------------------------------------------------------------------------
# 0. Dependencies + preflight: prove the model is actually enabled before we
#    build anything on top of it. (STS confirms which account we're in.)
# -----------------------------------------------------------------------------
banner "0. Install AWS deps + preflight (STS + Bedrock model access)"
$PY -m pip install -q -r requirements-aws.txt
aws sts get-caller-identity --query Account --output text
# Confirms BEDROCK_MODEL_ID is reachable in this account/region (one tiny call):
$PY -m tests.aws.check_access

# -----------------------------------------------------------------------------
# 1. CLIENT IDENTITY + DATA  ->  Amazon Cognito + Amazon DynamoDB
#    scripts/provision_portal.py  (writes var/portal-aws.json)
#    - Cognito user pool: client/staff sign-in, strong password policy,
#      admin-create-only, 60-min tokens, revocation on.
#    - DynamoDB table coherent-client-portal-v1 (pk/sk, SSE on, pay-per-request)
#      holds identities + synthetic client profiles.
# -----------------------------------------------------------------------------
banner "1. Cognito user pool + DynamoDB portal table"
$PY -m scripts.provision_portal

# -----------------------------------------------------------------------------
# 2. COMPLIANCE KNOWLEDGE  ->  Amazon Bedrock Knowledge Base + S3 + S3 Vectors + Titan v2
#    scripts/provision_knowledge_base.py  (writes var/knowledge-base.json)
#    - Reviewed public guidance (Reg BI) -> encrypted S3 bucket
#    - Embedded with amazon.titan-embed-text-v2:0 into an S3 Vectors index
#    - Wrapped in a Bedrock Knowledge Base; retrieval used by backend/aws/knowledge.py
#      (citations are only trusted when retrieved text contains the reviewed excerpt).
# -----------------------------------------------------------------------------
banner "2. Bedrock Knowledge Base (S3 source + S3 Vectors + Titan v2 embeddings)"
$PY -m scripts.provision_knowledge_base

# -----------------------------------------------------------------------------
# 3. SAFETY  ->  Amazon Bedrock Guardrails   (optional, recommended)
#    scripts/provision_guardrail.py  <- infra/guardrail.json  (writes var/guardrail-aws.json)
#    - Versioned guardrail that BLOCKS full SSNs + payment-card numbers in intake.
#    - Attached to every Converse call via guardrailConfig (backend/aws/bedrock_agent.py);
#      a guardrail_intervened stop reason hands the client to a human.
# -----------------------------------------------------------------------------
if [ "${SKIP_GUARDRAIL:-0}" != "1" ]; then
  banner "3. Bedrock Guardrail (PII block: SSN + card numbers)"
  $PY -m scripts.provision_guardrail
fi

# -----------------------------------------------------------------------------
# 4. VOICE VOCABULARY  ->  Amazon Transcribe   (optional; not wired to the demo UI)
#    backend/aws/transcribe.py
#    - Creates/refreshes custom vocabulary "samepage-financial-terms" so speech-to-text
#      biases toward Roth-IRA / RMD / 1099-R, etc. Browser Web Speech stays the demo default.
# -----------------------------------------------------------------------------
if [ "${WITH_TRANSCRIBE:-0}" = "1" ]; then
  banner "4. Transcribe financial custom vocabulary"
  $PY -m backend.aws.transcribe
fi

# Steps 5 (Bedrock Converse intake/triage/brief/plan) and Polly read-aloud need
# NO provisioning — they are pure runtime API calls (converse / synthesize_speech)
# made by backend/aws/bedrock_agent.py and backend/portal/speech.py once the model,
# KB, and (optional) guardrail above exist.

# -----------------------------------------------------------------------------
# DEPLOY (opt-in)  ->  Amazon EC2 + IAM + SSM + CloudFront + VPC/SG/EIP
#    scripts/deploy_aws.py + scripts/install_aws_host.sh
#    - Least-priv IAM instance role (only the exact Bedrock model/KB/guardrail/Polly actions)
#    - One t3.large Amazon Linux 2023, encrypted EBS, IMDSv2 required, NO SSH
#    - Security group opens :80 only to CloudFront's managed prefix list; CloudFront = HTTPS
#    - SSM send_command runs the sha-pinned installer; systemd serves FastAPI :8000 + Next :3200
#    Requires a clean, pushed `main` (the script enforces this).
# -----------------------------------------------------------------------------
if [ "${1:-}" = "--deploy" ]; then
  banner "DEPLOY: IAM role + EC2 host + SSM install + CloudFront HTTPS"
  $PY -m scripts.deploy_aws
  exit 0
fi

# -----------------------------------------------------------------------------
# LOCAL RUN (opt-in)  — same Bedrock/KB/Polly backend, no EC2/CloudFront.
# -----------------------------------------------------------------------------
if [ "${1:-}" = "--local" ]; then
  banner "LOCAL: smoke test on live Bedrock, then start the API"
  $PY -m tests.aws.smoke_live
  exec $PY -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
fi

banner "Provisioning complete. IDs saved under var/. Add --deploy or --local to run."
