"""Demo reset: clear sessions, cases, and assignments; reload reference data.

    python -m backend.reset

Equivalent to ``POST /demo/reset`` with the staff demo role while the server runs.
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


if __name__ == "__main__":
    main()
