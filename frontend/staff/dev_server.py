"""Local preview for the staff page. Development aid only; never the judged AI path.

Reuses contracts/mock_api.py, loads the expanded data/*.json in place of the frozen
fixture, serves this folder at /staff, and previews the spec's advisor routing order so
the page can be checked with three candidates. Agent 2 owns the real implementation.

Run from the repository root: python3 frontend/staff/dev_server.py
Then open http://127.0.0.1:8001/staff
"""

from __future__ import annotations

import copy
import importlib.util
import json
import mimetypes
import re
from http.server import ThreadingHTTPServer
from pathlib import Path

STAFF_DIR = Path(__file__).resolve().parent
ROOT = STAFF_DIR.parents[1]

_spec = importlib.util.spec_from_file_location("mock_api", ROOT / "contracts" / "mock_api.py")
mock_api = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mock_api)

DATA = {
    name: json.loads((ROOT / "data" / f"{name}.json").read_text())[name]
    for name in ("clients", "accounts", "events", "advisors", "glossary", "cases")
}
mock_api.FIXTURE.update(DATA)
mock_api.CASES.clear()
mock_api.CASES.update({case["case_id"]: copy.deepcopy(case) for case in DATA["cases"]})


def rank_candidates(case: dict) -> list[dict]:
    """Existing advisor first, then specialty match, availability, meeting mode, capacity."""
    if "fraud_or_security" in case["categories"]:
        return []
    client = next((c for c in DATA["clients"] if c["client_id"] == case["client_id"]), {})
    wanted = set(case["categories"])
    ranked = []
    for advisor in DATA["advisors"]:
        if not advisor["active"]:
            continue
        existing = advisor["advisor_id"] == client.get("existing_advisor_id")
        matched = [s for s in advisor["specialties"] if s in wanted]
        if not existing and not matched:
            continue
        meets = client.get("meeting_preference") in advisor["meeting_mode"]
        reasons = []
        if existing:
            reasons.append("Client's current advisor")
        if matched:
            reasons.append("Specialty match: " + ", ".join(m.replace("_", " ") for m in matched))
        reasons.append("available for a new case" if advisor["available"] else "not taking new cases")
        if meets:
            reasons.append("offers the client's preferred " + client["meeting_preference"].replace("_", " ") + " meetings")
        ranked.append((
            (not existing, not advisor["available"], -len(matched), not meets, -advisor["capacity"]),
            {
                "advisor_id": advisor["advisor_id"],
                "display_name": advisor["display_name"],
                "specialties": advisor["specialties"],
                "available": advisor["available"],
                "reason": "; ".join(reasons) + ".",
                "existing_client_relationship": existing,
            },
        ))
    return [candidate for _, candidate in sorted(ranked, key=lambda pair: pair[0])[:3]]


class Handler(mock_api.Handler):
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/staff", "/staff/"):
            return self._file("index.html")
        match = re.fullmatch(r"/staff/([\w.-]+\.(?:html|css|js))", path)
        if match:
            return self._file(match.group(1))
        match = re.fullmatch(r"/staff/cases/([^/]+)/candidates", path)
        if match and self.headers.get("X-Demo-Role") == "staff":
            case = mock_api.CASES.get(match.group(1))
            if case:
                return self._send(200, {"candidates": rank_candidates(case)})
        return super().do_GET()

    def _file(self, name: str):
        target = STAFF_DIR / name
        if not target.is_file():
            return self._error(404, "PATH_NOT_FOUND", "No such file.")
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", (mimetypes.guess_type(name)[0] or "text/plain") + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    print("Staff preview at http://127.0.0.1:8001/staff (fictional data; no AI)")
    ThreadingHTTPServer(("127.0.0.1", 8001), Handler).serve_forever()
