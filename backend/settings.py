"""Runtime settings for the SamePage backend (Agent 2).

Everything is read from environment variables so no credentials or machine
specific paths live in code. Agent 1 owns AWS configuration in
``backend/aws/config.py``; this module only decides *which* adapter to load.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

AGENT_MODES = ("mock", "bedrock")
DEMO_ROLES = ("client", "staff")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    agent_mode: str = field(default_factory=lambda: os.getenv("SAMEPAGE_AGENT_MODE", "mock").strip().lower())
    db_path: str = field(default_factory=lambda: os.getenv("SAMEPAGE_DB_PATH", str(REPO_ROOT / "var" / "samepage.db")))
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("SAMEPAGE_DATA_DIR", str(REPO_ROOT / "data"))))
    fallback_data_dir: Path = field(default_factory=lambda: REPO_ROOT / "backend" / "fixtures")
    default_demo_role: str = field(default_factory=lambda: os.getenv("SAMEPAGE_DEFAULT_DEMO_ROLE", "client").strip().lower())
    adapter_timeout_s: float = field(default_factory=lambda: float(os.getenv("SAMEPAGE_ADAPTER_TIMEOUT_S", "45")))
    client_frontend_dir: Path = field(default_factory=lambda: Path(os.getenv("SAMEPAGE_CLIENT_DIR", str(REPO_ROOT / "frontend" / "client"))))
    staff_frontend_dir: Path = field(default_factory=lambda: Path(os.getenv("SAMEPAGE_STAFF_DIR", str(REPO_ROOT / "frontend" / "staff"))))
    reset_on_start: bool = field(default_factory=lambda: _env_bool("SAMEPAGE_RESET_ON_START", False))

    def validate(self) -> "Settings":
        if self.agent_mode not in AGENT_MODES:
            raise ValueError(
                f"SAMEPAGE_AGENT_MODE={self.agent_mode!r} is not one of {AGENT_MODES}"
            )
        if self.default_demo_role not in DEMO_ROLES:
            raise ValueError(
                f"SAMEPAGE_DEFAULT_DEMO_ROLE={self.default_demo_role!r} is not one of {DEMO_ROLES}"
            )
        return self


def load_settings() -> Settings:
    return Settings().validate()
