"""Demo reset (INTEGRATION_RUNBOOK.md): restore the fictional seed state.

    python -m backend.reset_demo

Clears intake sessions, live cases, and assignments, then reloads clients,
accounts, events, advisors, glossary, and the optional seed cases from ``data/``
(or the fallback fixtures). The server does **not** need to restart: every
request reads SQLite, so a running app sees the reset on its next request.
``POST /demo/reset`` with the staff demo role does the same thing over HTTP.
"""

from __future__ import annotations

from backend.settings import load_settings
from backend.store import Store


def main() -> None:
    settings = load_settings()
    store = Store(settings.db_path, settings.data_dir, settings.fallback_data_dir)
    store.reset_state()
    counts = store.counts()
    store.close()
    print(f"reset complete: db={settings.db_path} data={store.data_source}")
    print(", ".join(f"{k}={v}" for k, v in counts.items()))
    print("Server restart not required.")


if __name__ == "__main__":
    main()
