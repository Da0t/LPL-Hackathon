"""Region and model configuration for the SamePage AWS adapter.

All values come from the environment so no credentials or account-specific
identifiers live in code. The backend and this adapter both read:

    AWS_REGION            default "us-east-1" (hackathon requirement)
    BEDROCK_MODEL_ID      required in "bedrock" mode; a model ID verified as
                          enabled in the event account whose name is on the
                          hackathon allowlist
    SAMEPAGE_AI_MODE      "bedrock" (live, judged path) or "stub" (offline
                          deterministic responses for dev only, never judged)

Optional tuning (sensible defaults so the demo works with just the three
variables above):

    BEDROCK_GUARDRAIL_ID / BEDROCK_GUARDRAIL_VERSION
                          attach a Bedrock Guardrail to every model call
    BEDROCK_MIN_INTERVAL_SECONDS   call pacing, default 1.0 (~1 call/sec)
    BEDROCK_MAX_RETRIES            bounded retries on throttle, default 3
    BEDROCK_BASE_BACKOFF_SECONDS   first backoff, doubles each retry
    BEDROCK_MAX_TOKENS / BEDROCK_TEMPERATURE
    BEDROCK_CONNECT_TIMEOUT / BEDROCK_READ_TIMEOUT
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_REGION = "us-east-1"
MODE_BEDROCK = "bedrock"
MODE_STUB = "stub"


@dataclass(frozen=True)
class AwsConfig:
    region: str
    model_id: str | None
    ai_mode: str
    guardrail_id: str | None
    guardrail_version: str | None
    min_interval_seconds: float
    max_retries: int
    base_backoff_seconds: float
    max_tokens: int
    temperature: float
    connect_timeout: float
    read_timeout: float

    @property
    def is_bedrock(self) -> bool:
        return self.ai_mode == MODE_BEDROCK

    def guardrail_payload(self) -> dict | None:
        """Return the Converse ``guardrailConfig`` block, or None if unset."""
        if self.guardrail_id and self.guardrail_version:
            return {
                "guardrailIdentifier": self.guardrail_id,
                "guardrailVersion": self.guardrail_version,
            }
        return None


def _get_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _get_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def load_config() -> AwsConfig:
    """Build an :class:`AwsConfig` from the current environment."""
    ai_mode = os.environ.get("SAMEPAGE_AI_MODE", MODE_BEDROCK).strip().lower()
    if ai_mode not in (MODE_BEDROCK, MODE_STUB):
        ai_mode = MODE_BEDROCK

    model_id = os.environ.get("BEDROCK_MODEL_ID") or None

    return AwsConfig(
        region=os.environ.get("AWS_REGION", DEFAULT_REGION) or DEFAULT_REGION,
        model_id=model_id,
        ai_mode=ai_mode,
        guardrail_id=os.environ.get("BEDROCK_GUARDRAIL_ID") or None,
        guardrail_version=os.environ.get("BEDROCK_GUARDRAIL_VERSION") or None,
        min_interval_seconds=_get_float("BEDROCK_MIN_INTERVAL_SECONDS", 1.0),
        max_retries=_get_int("BEDROCK_MAX_RETRIES", 3),
        base_backoff_seconds=_get_float("BEDROCK_BASE_BACKOFF_SECONDS", 0.75),
        max_tokens=_get_int("BEDROCK_MAX_TOKENS", 2048),
        temperature=_get_float("BEDROCK_TEMPERATURE", 0.2),
        connect_timeout=_get_float("BEDROCK_CONNECT_TIMEOUT", 5.0),
        read_timeout=_get_float("BEDROCK_READ_TIMEOUT", 30.0),
    )


def build_bedrock_client(cfg: AwsConfig):
    """Create a bedrock-runtime client using the default credential chain.

    No access keys are passed here; boto3 resolves credentials from the event
    account's supported mechanism (SSO/role/profile/instance). We disable
    botocore's own retries because this adapter paces and retries explicitly.
    """
    import boto3
    from botocore.config import Config

    return boto3.client(
        "bedrock-runtime",
        region_name=cfg.region,
        config=Config(
            connect_timeout=cfg.connect_timeout,
            read_timeout=cfg.read_timeout,
            retries={"max_attempts": 0, "mode": "standard"},
        ),
    )
