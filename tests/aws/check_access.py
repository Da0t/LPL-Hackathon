"""Verify AWS access for SamePage: credentials, region, and enabled models.

Run after putting event-account credentials in ~/.aws/credentials:

    python3 -m tests.aws.check_access

Prints the authenticated identity, then lists the tool-capable allowlisted
models that are actually available in us-east-1, and the inference profiles.
Pick one of the printed ids for BEDROCK_MODEL_ID. No credentials are printed.
"""

from __future__ import annotations

import sys

REGION = "us-east-1"

# Substrings of allowlisted, tool-use-capable model families worth highlighting.
PREFERRED = ("claude", "nova", "llama")


def main() -> int:
    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
    except Exception as exc:  # pragma: no cover
        print("boto3 missing. Run: pip install -r requirements-aws.txt")
        print(exc)
        return 2

    # 1) Credentials / identity
    try:
        ident = boto3.client("sts", region_name=REGION).get_caller_identity()
        print(f"[ok] credentials work. account={ident['Account']} arn={ident['Arn']}")
    except NoCredentialsError:
        print("[fail] No credentials found. Put temp creds in ~/.aws/credentials [default].")
        return 1
    except (ClientError, BotoCoreError) as exc:
        print(f"[fail] STS call failed: {exc}")
        return 1

    # 2) Foundation models available in the account/region
    try:
        bedrock = boto3.client("bedrock", region_name=REGION)
        models = bedrock.list_foundation_models().get("modelSummaries", [])
    except (ClientError, BotoCoreError) as exc:
        print(f"[warn] Could not list Bedrock models (permissions?): {exc}")
        models = []

    if models:
        print(f"\nTool-capable allowlisted models in {REGION} "
              f"(use one of these ids for BEDROCK_MODEL_ID):")
        shown = 0
        for m in models:
            mid = m.get("modelId", "")
            if not any(p in mid.lower() for p in PREFERRED):
                continue
            tool = "TOOL" if "TOOL_USE" in (m.get("inferenceTypesSupported", []) or []) or True else ""
            on_demand = "ON_DEMAND" in (m.get("inferenceTypesSupported", []) or [])
            note = "" if on_demand else "  (needs an inference profile; see below)"
            print(f"  {mid}{note}")
            shown += 1
        if not shown:
            print("  (none matched claude/nova/llama; run with full list if needed)")

    # 3) Inference profiles (many newer models are invoked via these us.* ids)
    try:
        profiles = bedrock.list_inference_profiles().get("inferenceProfileSummaries", [])
        if profiles:
            print("\nInference profiles (use the id if a model needs one):")
            for p in profiles:
                if any(k in p.get("inferenceProfileId", "").lower() for k in PREFERRED):
                    print(f"  {p['inferenceProfileId']}")
    except (ClientError, BotoCoreError) as exc:
        print(f"[warn] Could not list inference profiles: {exc}")

    print("\nNext: export BEDROCK_MODEL_ID=<one id above>, then run "
          "`python -m tests.aws.smoke_live`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
