"""Live Bedrock smoke test with synthetic data. Requires real credentials.

Run (from repo root) after exporting event-account credentials:

    export AWS_REGION=us-east-1
    export BEDROCK_MODEL_ID=<verified allowlisted model id>
    export SAMEPAGE_AI_MODE=bedrock
    python -m tests.aws.smoke_live

Prints the live intake interpretation for the "Roth thing from my old job"
scenario (expect: it notices there is no Roth IRA and asks about the rollover
IRA), then the live triage of a security case (expect: routes to specialist
review). No assertions on exact wording; this confirms the model, region,
credentials, tool-use loop, and pacing all work end to end.
"""

from __future__ import annotations

import json
import sys

from backend.aws import intake_turn, triage_case
from backend.aws.config import load_config
from tests.aws.fixtures import FixtureTools


def main() -> int:
    cfg = load_config()
    print(f"region={cfg.region} model_id={cfg.model_id} mode={cfg.ai_mode} "
          f"guardrail={'on' if cfg.guardrail_payload() else 'off'}")
    if not cfg.is_bedrock or not cfg.model_id:
        print("Set SAMEPAGE_AI_MODE=bedrock and BEDROCK_MODEL_ID first.")
        return 2

    tools = FixtureTools()

    print("\n=== INTAKE: 'Roth thing from my old job' (CLIENT-017) ===")
    intake = intake_turn(
        "CLIENT-017",
        "I need six thousand dollars from the Roth thing from my old job.",
        None,
        tools,
    )
    print(json.dumps(intake, indent=2, ensure_ascii=False))

    print("\n=== TRIAGE: unrecognized sign-in (security) ===")
    triage = triage_case(
        {"confirmed_plain_language_request":
         "I need help reviewing an account sign-in I do not recognize.",
         "original_words": "I don't recognize a sign-in alert on my account."},
        tools,
    )
    print(json.dumps(triage, indent=2, ensure_ascii=False))

    ok = bool(intake.get("question")) and "fraud_or_security" in triage.get("categories", [])
    print("\nSMOKE RESULT:", "PASS" if ok else "CHECK OUTPUT ABOVE")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
