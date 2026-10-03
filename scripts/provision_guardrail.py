"""Create a versioned PII Guardrail for the synthetic Coherent demo."""

import json
import os
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "infra/guardrail.json").read_text())
OUTPUT = ROOT / "var/guardrail-aws.json"
client = boto3.client("bedrock", region_name="us-east-1")


def main():
    if OUTPUT.exists():
        saved = json.loads(OUTPUT.read_text())
        current = client.get_guardrail(
            guardrailIdentifier=saved["guardrail_id"],
            guardrailVersion=saved["version"],
        )
        if current["status"] == "READY":
            print("Guardrail ready:", saved["guardrail_id"], "version", saved["version"])
            return
    existing = [
        item for item in client.list_guardrails(maxResults=100)["guardrails"]
        if item["name"] == CONFIG["name"]
    ]
    if existing:
        guardrail_id = existing[0]["id"]
        client.update_guardrail(guardrailIdentifier=guardrail_id, **CONFIG)
    else:
        guardrail_id = client.create_guardrail(**CONFIG)["guardrailId"]
    version = client.create_guardrail_version(
        guardrailIdentifier=guardrail_id,
        description="Coherent hosted demo PII policy",
    )["version"]
    OUTPUT.parent.mkdir(exist_ok=True)
    fd = os.open(OUTPUT, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump({"guardrail_id": guardrail_id, "version": version, "region": "us-east-1"}, handle, indent=2)
        handle.write("\n")
    print("Guardrail ready:", guardrail_id, "version", version)


if __name__ == "__main__":
    main()
