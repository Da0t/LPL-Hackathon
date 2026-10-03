"""Local SQLite repository for SamePage (Agent 2).

Reference data (clients, accounts, events, advisors, glossary) is loaded from
Agent 4's ``data/`` directory when all five files are present and valid, and
from ``backend/fixtures/`` otherwise. The backend never writes to those files.
Application state (intake sessions, cases, assignments) lives in SQLite so the
client and staff pages share one source of truth across requests.

The adapter (Agent 1) never touches this module directly; it only receives the
authorized tool callbacks built in ``backend/services/tools.py``.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
from pathlib import Path
from typing import Any, Iterable

log = logging.getLogger("samepage.store")

SEED_FILES: tuple[str, ...] = ("clients", "accounts", "events", "advisors", "glossary")
FIRST_CASE_NUMBER = 1042  # matches the example CASE-1042 in the product spec

_SCHEMA = """
CREATE TABLE IF NOT EXISTS clients  (client_id TEXT PRIMARY KEY, doc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS accounts (account_id TEXT PRIMARY KEY, client_id TEXT NOT NULL, doc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events   (event_id TEXT PRIMARY KEY, account_id TEXT NOT NULL, doc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS advisors (advisor_id TEXT PRIMARY KEY, doc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS glossary (key TEXT PRIMARY KEY, doc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    client_id  TEXT NOT NULL,
    status     TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    doc        TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cases (
    case_id    TEXT PRIMARY KEY,
    case_num   INTEGER NOT NULL,
    client_id  TEXT NOT NULL,
    status     TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    doc        TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assignments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id      TEXT NOT NULL,
    advisor_id   TEXT NOT NULL,
    staff_reason TEXT NOT NULL,
    decided_by   TEXT NOT NULL,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_accounts_client ON accounts(client_id);
CREATE INDEX IF NOT EXISTS idx_events_account ON events(account_id);
CREATE INDEX IF NOT EXISTS idx_cases_created ON cases(created_at);
"""


class SeedDataError(RuntimeError):
    """Raised when neither the primary nor the fallback seed data is usable."""


# --------------------------------------------------------------------------
# Record normalization (tolerant to the most likely alternative field names)
# --------------------------------------------------------------------------


def _first(record: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in record and record[name] is not None:
            return record[name]
    return default


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    if isinstance(value, str):
        parts = [p.strip() for p in re.split(r"[,;/|]", value) if p.strip()]
        return parts
    return [value]


def _as_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    if text in {"true", "yes", "y", "1", "active", "available", "open"}:
        return True
    if text in {"false", "no", "n", "0", "inactive", "unavailable", "on_leave", "closed", "full"}:
        return False
    return default


def _as_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").replace("$", "").strip())
    except ValueError:
        return None


def _mask(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "****"
    if text.startswith("*"):
        return text
    digits = re.sub(r"\D", "", text)
    return "****" + (digits[-4:] if digits else text[-4:])


def normalize_client(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "client_id": str(_first(raw, "client_id", "id")),
        "display_name": str(_first(raw, "display_name", "name", "full_name", default="Client")),
        "preferred_contact_channel": _first(raw, "preferred_contact_channel", "contact_preference", "meeting_preference", "preferred_channel"),
        "existing_advisor_id": _first(raw, "existing_advisor_id", "advisor_id", "primary_advisor_id"),
        "state": _first(raw, "state", "region"),
        "demo_scenario": _first(raw, "demo_scenario", "scenario", "notes"),
    }


def normalize_account(raw: dict[str, Any]) -> dict[str, Any]:
    account_id = str(_first(raw, "account_id", "id"))
    masked = _first(raw, "masked_identifier", "masked_id", "masked_number", "last4", "last_four")
    return {
        "account_id": account_id,
        "client_id": str(_first(raw, "client_id", "owner_client_id", "owner_id", "client")),
        "account_type": str(_first(raw, "account_type", "type", default="unknown")).strip().lower().replace(" ", "_"),
        "label": str(_first(raw, "label", "name", "account_name", "display_name", default=account_id)),
        "familiar_label": _first(raw, "familiar_label", "nickname", "plain_label"),
        "masked_identifier": _mask(masked),
        "ownership": _first(raw, "ownership", "relationship", "registration"),
        "former_employer": _first(raw, "former_employer", "employer", "plan_sponsor"),
        "balance": _as_number(_first(raw, "balance", "balance_snapshot", "current_balance")),
        "balance_as_of": _first(raw, "balance_as_of", "as_of", "balance_date", "snapshot_date"),
        "source_id": _first(raw, "source_id", "source", "record_id", default=f"SNAP-{account_id}"),
        "status": str(_first(raw, "status", default="open")).lower(),
    }


def normalize_event(raw: dict[str, Any]) -> dict[str, Any]:
    event_id = _first(raw, "event_id", "id", "source_id")
    return {
        "event_id": str(event_id),
        "account_id": str(_first(raw, "account_id", "account")),
        "type": str(_first(raw, "type", "event_type", "kind", default="event")).strip().lower().replace(" ", "_"),
        "date": str(_first(raw, "date", "event_date", "occurred_at", "timestamp", default="")),
        "source_id": str(_first(raw, "source_id", "source", default=event_id)),
        "description": _first(raw, "description", "summary", "note", "details"),
    }


def normalize_advisor(raw: dict[str, Any]) -> dict[str, Any]:
    active_raw = _first(raw, "active", "is_active", "status")
    available_raw = _first(raw, "available", "availability", "is_available", "accepting_clients")
    capacity = _as_number(_first(raw, "capacity", "open_slots", "remaining_capacity"))
    advisor = {
        "advisor_id": str(_first(raw, "advisor_id", "id")),
        "display_name": str(_first(raw, "display_name", "name", default="Advisor")),
        "kind": str(_first(raw, "kind", "type", default="advisor")),
        "specialties": [str(s).strip().lower().replace(" ", "_") for s in _as_list(_first(raw, "specialties", "specialty_tags", "tags", "specialty"))],
        "region": _first(raw, "region", "state", "state_region"),
        "meeting_modes": [str(m).strip().lower().replace(" ", "_").replace("-", "_") for m in _as_list(_first(raw, "meeting_modes", "meeting_mode", "modes"))],
        "capacity": int(capacity) if capacity is not None else None,
        "available": _as_bool(available_raw, default=True),
        "active": _as_bool(active_raw, default=True),
        "next_available": _first(raw, "next_available", "next_availability", "next_open_slot"),
        "existing_client_ids": [str(c) for c in _as_list(_first(raw, "existing_client_ids", "existing_clients", "client_ids", "clients"))],
    }
    if advisor["capacity"] is not None and advisor["capacity"] <= 0 and available_raw is None:
        advisor["available"] = False
    return advisor


def normalize_glossary_entry(raw: dict[str, Any]) -> dict[str, Any]:
    term = str(_first(raw, "term", "name", "title", default=""))
    key = str(_first(raw, "key", "id", default=re.sub(r"[^a-z0-9]+", "_", term.lower()).strip("_")))
    return {
        "key": key,
        "term": term or key.replace("_", " ").title(),
        "aliases": [str(a) for a in _as_list(_first(raw, "aliases", "synonyms", "also_called"))],
        "plain": str(_first(raw, "plain", "definition", "plain_explanation", "explanation", "plain_language", default="")),
    }


_NORMALIZERS = {
    "clients": normalize_client,
    "accounts": normalize_account,
    "events": normalize_event,
    "advisors": normalize_advisor,
    "glossary": normalize_glossary_entry,
}


def _unwrap_records(name: str, payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        for key in (name, "items", "data", "records", "entries", "terms"):
            if isinstance(payload.get(key), list):
                records = payload[key]
                break
        else:
            # A dict keyed by id, e.g. {"CLIENT-017": {...}}
            records = []
            for key, value in payload.items():
                if isinstance(value, dict):
                    value = dict(value)
                    value.setdefault("id", key)
                    records.append(value)
    else:
        raise ValueError(f"{name}.json must contain a list or an object")
    return [r for r in records if isinstance(r, dict)]


_REPO_ROOT = Path(__file__).resolve().parent.parent


def _display_path(path: Path) -> str:
    """Repo-relative path for logs and /health so machine paths never leak into docs."""
    try:
        return str(path.resolve().relative_to(_REPO_ROOT))
    except ValueError:
        return str(path)


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


# --------------------------------------------------------------------------
# Store
# --------------------------------------------------------------------------


class Store:
    def __init__(self, db_path: str, data_dir: Path | str, fallback_dir: Path | str):
        self.db_path = str(db_path)
        self.data_dir = Path(data_dir)
        self.fallback_dir = Path(fallback_dir)
        self.data_source = "unloaded"
        self._lock = threading.RLock()
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            if self.db_path != ":memory:":
                self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(_SCHEMA)

    # ---------------------------------------------------------------- seeding

    def _read_seed_dir(self, directory: Path) -> dict[str, list[dict[str, Any]]] | None:
        if not directory.is_dir():
            return None
        loaded: dict[str, list[dict[str, Any]]] = {}
        for name in SEED_FILES:
            path = directory / f"{name}.json"
            if not path.is_file():
                log.info("seed file missing: %s", path)
                return None
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                records = [_NORMALIZERS[name](r) for r in _unwrap_records(name, payload)]
            except (OSError, ValueError, KeyError, TypeError) as exc:
                log.warning("seed file unusable: %s (%s)", path, exc)
                return None
            if not records:
                log.warning("seed file has no records: %s", path)
                return None
            loaded[name] = records
        return loaded

    def load_seed(self) -> str:
        """Load reference data, preferring Agent 4's data/ directory."""
        seed = self._read_seed_dir(self.data_dir)
        source = _display_path(self.data_dir)
        if seed is None:
            seed = self._read_seed_dir(self.fallback_dir)
            source = f"{_display_path(self.fallback_dir)} (fallback fixtures)"
            if seed is None:
                raise SeedDataError(
                    f"No usable seed data in {self.data_dir} or {self.fallback_dir}"
                )
        self._warn_integrity(seed)
        with self._lock:
            self._conn.execute("BEGIN")
            try:
                for table in ("clients", "accounts", "events", "advisors", "glossary"):
                    self._conn.execute(f"DELETE FROM {table}")
                self._conn.executemany(
                    "INSERT INTO clients(client_id, doc) VALUES (?, ?)",
                    [(c["client_id"], json.dumps(c)) for c in seed["clients"]],
                )
                self._conn.executemany(
                    "INSERT INTO accounts(account_id, client_id, doc) VALUES (?, ?, ?)",
                    [(a["account_id"], a["client_id"], json.dumps(a)) for a in seed["accounts"]],
                )
                self._conn.executemany(
                    "INSERT OR REPLACE INTO events(event_id, account_id, doc) VALUES (?, ?, ?)",
                    [(e["event_id"], e["account_id"], json.dumps(e)) for e in seed["events"]],
                )
                self._conn.executemany(
                    "INSERT INTO advisors(advisor_id, doc) VALUES (?, ?)",
                    [(a["advisor_id"], json.dumps(a)) for a in seed["advisors"]],
                )
                self._conn.executemany(
                    "INSERT OR REPLACE INTO glossary(key, doc) VALUES (?, ?)",
                    [(g["key"], json.dumps(g)) for g in seed["glossary"]],
                )
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
        self.data_source = source
        log.info("seed data loaded from %s", source)
        return source

    @staticmethod
    def _warn_integrity(seed: dict[str, list[dict[str, Any]]]) -> None:
        client_ids = {c["client_id"] for c in seed["clients"]}
        account_ids = {a["account_id"] for a in seed["accounts"]}
        advisor_ids = {a["advisor_id"] for a in seed["advisors"]}
        for account in seed["accounts"]:
            if account["client_id"] not in client_ids:
                log.warning("account %s references unknown client %s", account["account_id"], account["client_id"])
        for event in seed["events"]:
            if event["account_id"] not in account_ids:
                log.warning("event %s references unknown account %s", event["event_id"], event["account_id"])
        for client in seed["clients"]:
            adv = client.get("existing_advisor_id")
            if adv and adv not in advisor_ids:
                log.warning("client %s references unknown advisor %s", client["client_id"], adv)

    def reset_state(self) -> None:
        """Clear sessions, cases, and assignments; reload reference data."""
        with self._lock:
            self._conn.execute("BEGIN")
            try:
                for table in ("sessions", "cases", "assignments"):
                    self._conn.execute(f"DELETE FROM {table}")
                self._conn.execute("DELETE FROM sqlite_sequence WHERE name='assignments'")
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
        self.load_seed()

    def counts(self) -> dict[str, int]:
        with self._lock:
            out = {}
            for table in ("clients", "accounts", "events", "advisors", "glossary", "sessions", "cases", "assignments"):
                out[table] = int(self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            return out

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ------------------------------------------------------------ reference

    def _docs(self, sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(sql, tuple(params)).fetchall()
        return [json.loads(row["doc"]) for row in rows]

    def _doc(self, sql: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(sql, tuple(params)).fetchone()
        return json.loads(row["doc"]) if row else None

    def list_clients(self) -> list[dict[str, Any]]:
        return self._docs("SELECT doc FROM clients ORDER BY client_id")

    def get_client(self, client_id: str) -> dict[str, Any] | None:
        return self._doc("SELECT doc FROM clients WHERE client_id = ?", (client_id,))

    def accounts_for_client(self, client_id: str) -> list[dict[str, Any]]:
        return self._docs("SELECT doc FROM accounts WHERE client_id = ? ORDER BY account_id", (client_id,))

    def get_account(self, account_id: str) -> dict[str, Any] | None:
        return self._doc("SELECT doc FROM accounts WHERE account_id = ?", (account_id,))

    def events_for_account(self, account_id: str) -> list[dict[str, Any]]:
        events = self._docs("SELECT doc FROM events WHERE account_id = ?", (account_id,))
        return sorted(events, key=lambda e: e.get("date") or "", reverse=True)

    def list_advisors(self) -> list[dict[str, Any]]:
        return self._docs("SELECT doc FROM advisors ORDER BY advisor_id")

    def get_advisor(self, advisor_id: str) -> dict[str, Any] | None:
        return self._doc("SELECT doc FROM advisors WHERE advisor_id = ?", (advisor_id,))

    def existing_advisor_id(self, client_id: str) -> str | None:
        client = self.get_client(client_id)
        if client and client.get("existing_advisor_id"):
            return str(client["existing_advisor_id"])
        for advisor in self.list_advisors():
            if client_id in advisor.get("existing_client_ids", []):
                return advisor["advisor_id"]
        return None

    def list_glossary(self) -> list[dict[str, Any]]:
        return self._docs("SELECT doc FROM glossary ORDER BY key")

    def glossary_lookup(self, term: str) -> dict[str, Any] | None:
        wanted = normalize_text(term)
        if not wanted:
            return None
        for entry in self.list_glossary():
            names = {normalize_text(entry["key"].replace("_", " ")), normalize_text(entry["term"])}
            names.update(normalize_text(a) for a in entry.get("aliases", []))
            if wanted in names:
                return entry
        # Prefix/contains match as a second pass ("roth" -> Roth IRA)
        for entry in self.list_glossary():
            names = [normalize_text(entry["term"])] + [normalize_text(a) for a in entry.get("aliases", [])]
            if any(n and (n.startswith(wanted) or wanted.startswith(n)) for n in names):
                return entry
        return None

    def glossary_terms_in_text(self, text: str) -> list[dict[str, Any]]:
        """Approved glossary entries whose term or alias appears in the text."""
        haystack = f" {normalize_text(text)} "
        found: list[dict[str, Any]] = []
        for entry in self.list_glossary():
            names = [entry["term"]] + list(entry.get("aliases", []))
            for name in names:
                needle = normalize_text(name)
                if needle and f" {needle} " in haystack:
                    found.append(entry)
                    break
        return found

    # -------------------------------------------------------------- sessions

    def save_session(self, session: dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO sessions(session_id, client_id, status, created_at, updated_at, doc) VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(session_id) DO UPDATE SET status=excluded.status, updated_at=excluded.updated_at, doc=excluded.doc",
                (
                    session["session_id"], session["client_id"], session["status"],
                    session["created_at"], session["updated_at"], json.dumps(session),
                ),
            )

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        return self._doc("SELECT doc FROM sessions WHERE session_id = ?", (session_id,))

    # ----------------------------------------------------------------- cases

    def next_case_id(self) -> str:
        with self._lock:
            row = self._conn.execute("SELECT MAX(case_num) FROM cases").fetchone()
        current = row[0] if row and row[0] is not None else FIRST_CASE_NUMBER - 1
        return f"CASE-{int(current) + 1}"

    def save_case(self, case: dict[str, Any]) -> None:
        case_num = int(case["case_id"].rsplit("-", 1)[-1])
        with self._lock:
            self._conn.execute(
                "INSERT INTO cases(case_id, case_num, client_id, status, created_at, updated_at, doc) VALUES (?,?,?,?,?,?,?) "
                "ON CONFLICT(case_id) DO UPDATE SET status=excluded.status, updated_at=excluded.updated_at, doc=excluded.doc",
                (
                    case["case_id"], case_num, case["client_id"], case["status"],
                    case["created_at"], case["updated_at"], json.dumps(case),
                ),
            )

    def get_case(self, case_id: str) -> dict[str, Any] | None:
        return self._doc("SELECT doc FROM cases WHERE case_id = ?", (case_id,))

    def list_cases(self) -> list[dict[str, Any]]:
        return self._docs("SELECT doc FROM cases ORDER BY created_at DESC, case_num DESC")

    def record_assignment(self, case_id: str, advisor_id: str, staff_reason: str, decided_by: str, created_at: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO assignments(case_id, advisor_id, staff_reason, decided_by, created_at) VALUES (?,?,?,?,?)",
                (case_id, advisor_id, staff_reason, decided_by, created_at),
            )

    def assignments_for_case(self, case_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT case_id, advisor_id, staff_reason, decided_by, created_at FROM assignments WHERE case_id = ? ORDER BY id",
                (case_id,),
            ).fetchall()
        return [dict(row) for row in rows]
