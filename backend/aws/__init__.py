"""SamePage AWS integration (Agent 1).

Public adapter surface imported by the backend (Agent 2):

    from backend.aws import intake_turn, triage_case

Everything AWS-specific (Bedrock calls, prompts, tool-use loop, pacing,
retries, optional Guardrails and Transcribe) lives in this package. The
adapter never reads storage directly; the backend supplies authorized tool
callbacks. See ``AWS_SETUP.md`` for configuration and the live smoke test.
"""

from .bedrock_agent import (
    BedrockAdapterError,
    advisor_brief,
    intake_turn,
    triage_case,
)
from .config import AwsConfig, load_config

__all__ = [
    "intake_turn",
    "triage_case",
    "advisor_brief",
    "BedrockAdapterError",
    "AwsConfig",
    "load_config",
]
