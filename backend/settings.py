"""Runtime settings for the SamePage backend (Agent 2).

Everything is read from environment variables so no credentials or machine
specific paths live in code. Agent 1 owns AWS configuration (``AWS_REGION``,
``BEDROCK_MODEL_ID``) in ``backend/aws/config.py``; this module only decides
*which* language-model adapter to load:

``SAMEPAGE_AI_MODE=bedrock``  Agent 1's live Bedrock adapter (the judged path; README.md)
``SAMEPAGE_AI_MODE=stub``     Agent 1's adapter in its offline stub mode (needs backend/aws present)
``SAMEPAGE_AI_MODE=mock``     Agent 2's deterministic mock (default; offline UI development)

``SAMEPAGE_AGENT_MODE`` is accepted as a legacy alias.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

AI_MODES = ("mock", "stub", "bedrock")
DEMO_ROLES = ("client", "staff")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_mode() -> str:
    raw = os.getenv("SAMEPAGE_AI_MODE") or os.getenv("SAMEPAGE_AGENT_MODE") or "mock"
    return raw.strip().lower()


@dataclass(frozen=True)
class Settings:
    ai_mode: str = field(default_factory=_env_mode)
    db_path: str = field(default_factory=lambda: os.getenv("SAMEPAGE_DB_PATH", str(REPO_ROOT / "var" / "samepage.db")))
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("SAMEPAGE_DATA_DIR", str(REPO_ROOT / "data"))))
    fallback_data_dir: Path = field(default_factory=lambda: REPO_ROOT / "backend" / "fixtures")
    default_demo_role: str = field(default_factory=lambda: os.getenv("SAMEPAGE_DEFAULT_DEMO_ROLE", "client").strip().lower())
    adapter_timeout_s: float = field(default_factory=lambda: float(os.getenv("SAMEPAGE_ADAPTER_TIMEOUT_S", "90")))
    client_frontend_dir: Path = field(default_factory=lambda: Path(os.getenv("SAMEPAGE_CLIENT_DIR", str(REPO_ROOT / "frontend" / "client"))))
    staff_frontend_dir: Path = field(default_factory=lambda: Path(os.getenv("SAMEPAGE_STAFF_DIR", str(REPO_ROOT / "frontend" / "staff"))))
    reset_on_start: bool = field(default_factory=lambda: _env_bool("SAMEPAGE_RESET_ON_START", False))

    # Backwards-compatible name used by earlier code and docs.
    @property
    def agent_mode(self) -> str:
        return self.ai_mode

    def validate(self) -> "Settings":
        if self.ai_mode not in AI_MODES:
            raise ValueError(f"SAMEPAGE_AI_MODE={self.ai_mode!r} is not one of {AI_MODES}")
        if self.default_demo_role not in DEMO_ROLES:
            raise ValueError(f"SAMEPAGE_DEFAULT_DEMO_ROLE={self.default_demo_role!r} is not one of {DEMO_ROLES}")
        return self


def load_settings() -> Settings:
    return Settings().validate()
