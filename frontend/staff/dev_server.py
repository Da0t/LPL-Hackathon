"""Local preview for the staff page. Development aid only; never the judged AI path.

Reuses contracts/mock_api.py, loads the expanded data/*.json in place of the frozen
fixture, serves this folder at /staff, and previews the spec's advisor routing order so
the page can be checked with three candidates. Agent 2 owns the real implementation.

Run from the repository root:

    python3 frontend/staff/dev_server.py            # version-one responses
    python3 frontend/staff/dev_server.py --v2       # adds the optional fields proposed
                                                    # in data/CONTRACT_V2_PROPOSAL.md
    python3 frontend/staff/dev_server.py --port 8002

Then open http://127.0.0.1:8001/staff
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import mimetypes
import re
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.dont_write_bytecode = True  # keep contracts/ free of __pycache__

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

V2 = False
STATIC = re.compile(r"/staff/((?:fonts/)?[\w.-]+\.(?:html|css|js|woff2))")


def _client(case: dict) -> dict:
    return next((c for c in DATA["clients"] if c["client_id"] == case["client_id"]), {})


def rank_candidates(case: dict) -> list[dict]:
    """Existing advisor first, then availability, specialty match, meeting mode, capacity."""
    if "fraud_or_security" in case["categories"]:
        return []
    client = _client(case)
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
        candidate = {
            "advisor_id": advisor["advisor_id"],
            "display_name": advisor["display_name"],
            "specialties": advisor["specialties"],
            "available": advisor["available"],
            "reason": "; ".join(reasons) + ".",
        }
        if V2:
            candidate.update(
                existing_client_relationship=existing,
                meeting_mode=advisor["meeting_mode"],
                capacity=advisor["capacity"],
            )
        ranked.append((
            (not existing, not advisor["available"], -len(matched), not meets, -advisor["capacity"]),
            candidate,
        ))
    return [candidate for _, candidate in sorted(ranked, key=lambda pair: pair[0])[:3]]


def with_v2_fields(case: dict) -> dict:
    """Attach the proposed optional fields, each taken from a record with a source ID."""
    case = copy.deepcopy(case)
    client = _client(case)
    case["preferred_contact_channel"] = client.get("preferred_contact_channel")
    case["client_confirmed_at"] = case["created_at"]
    account = next((a for a in DATA["accounts"] if a["account_id"] == case["selected_account_id"]), None)
    context = case["account_context"]
    if context and account:
        context["familiar_label"] = account["familiar_label"]
        context["currency"] = account["currency"]
        summaries = {e["source_id"]: e["summary"] for e in DATA["events"]}
        for event in context["relevant_events"]:
            event["summary"] = summaries.get(event["source_id"])
        if "client_term_did_not_match_account_type" in case["flags"]:
            held = {a["account_type"] for a in DATA["accounts"] if a["client_id"] == case["client_id"]}
            if "roth" in case["original_words"].lower() and "roth_ira" not in held:
                case["conflicts"] = [{
                    "statement": "Client said Roth; no Roth IRA appears in the client's authorized account list. "
                                 "The confirmed account is a rollover IRA.",
                    "source_id": account["source_id"],
                }]
    return case


class Handler(mock_api.Handler):
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/staff", "/staff/"):
            return self._file("index.html")
        match = STATIC.fullmatch(path)
        if match:
            return self._file(match.group(1))
        if self.headers.get("X-Demo-Role") == "staff":
            match = re.fullmatch(r"/staff/cases/([^/]+)/candidates", path)
            if match and match.group(1) in mock_api.CASES:
                return self._send(200, {"candidates": rank_candidates(mock_api.CASES[match.group(1)])})
            match = re.fullmatch(r"/staff/cases/([^/]+)", path)
            if V2 and match and match.group(1) in mock_api.CASES:
                return self._send(200, with_v2_fields(mock_api.CASES[match.group(1)]))
        return super().do_GET()

    def _file(self, name: str):
        target = STAFF_DIR / name
        if not target.is_file():
            return self._error(404, "PATH_NOT_FOUND", "No such file.")
        body = target.read_bytes()
        kind = mimetypes.guess_type(name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", kind + ("; charset=utf-8" if kind.startswith("text") or name.endswith(".js") else ""))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # keep the terminal quiet while the page polls
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--v2", action="store_true", help="add the proposed optional version-two fields")
    args = parser.parse_args()
    V2 = args.v2
    print(f"Staff preview at http://127.0.0.1:{args.port}/staff "
          f"({'proposed v2 fields' if V2 else 'v1 responses'}; fictional data; no AI)", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
