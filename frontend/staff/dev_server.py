"""Local preview server. Development and contingency aid; it is not Agent 2's backend.

Serves the site at /site, the staff page at /staff (and the client page at /client when
that folder is present) together with the version-one API on one origin, using the fictional data in
data/*.json. Standard library only.

Run from the repository root:

    python3 frontend/staff/dev_server.py              # preset answers from contracts/mock_api.py
    python3 frontend/staff/dev_server.py --v2         # also send the optional fields proposed
                                                      # in data/CONTRACT_V2_PROPOSAL.md
    python3 frontend/staff/dev_server.py --ai adapter # intake and triage go through Agent 1's
                                                      # backend.aws adapter (needs that branch)

With --ai adapter the adapter decides between live Bedrock and its offline stub from
SAMEPAGE_AI_MODE, exactly as it will under the real backend. Only the Bedrock mode is a
judged AI path; the preset and stub modes must never be presented as the AI demo.

Then open http://127.0.0.1:8001/staff
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import mimetypes
import re
import sys
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.dont_write_bytecode = True  # keep the repository free of __pycache__

STAFF_DIR = Path(__file__).resolve().parent
ROOT = STAFF_DIR.parents[1]
sys.path.insert(0, str(ROOT))

from data.store import Store  # noqa: E402

_spec = importlib.util.spec_from_file_location("mock_api", ROOT / "contracts" / "mock_api.py")
mock_api = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mock_api)

STORE = Store()
mock_api.FIXTURE.update(STORE.data)
mock_api.CASES.clear()
mock_api.CASES.update({case["case_id"]: copy.deepcopy(case) for case in STORE.data["cases"]})

V2 = False
ADAPTER = None  # Agent 1's backend.aws module when --ai adapter is used
STATIC = re.compile(r"/(staff|client|site)/((?:[\w-]+/)*[\w.-]+\.(?:html|css|js|woff2|png|svg))")


def with_v2_fields(case: dict) -> dict:
    """Attach the proposed optional fields, each taken from a record with a source ID."""
    case = copy.deepcopy(case)
    client = STORE.client(case["client_id"]) or {}
    case["preferred_contact_channel"] = client.get("preferred_contact_channel")
    case.setdefault("client_confirmed_at", case["created_at"])
    if case["account_context"]:
        events = [e["source_id"] for e in case["account_context"]["relevant_events"]]
        extended = STORE.account_context(case["selected_account_id"], extended=True)
        extended["relevant_events"] = [e for e in extended["relevant_events"] if e["source_id"] in events]
        case["account_context"] = extended
        conflicts = STORE.wording_conflicts(case["client_id"], case["original_words"], case["selected_account_id"])
        if conflicts and "client_term_did_not_match_account_type" in case["flags"]:
            case["conflicts"] = conflicts
    return case


class Handler(mock_api.Handler):
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/staff", "/staff/"):
            return self._file(STAFF_DIR / "index.html")
        if path in ("/", "/site"):
            self.send_response(302)
            self.send_header("Location", "/site/")
            self.send_header("Content-Length", "0")
            return self.end_headers()
        if path == "/site/":
            return self._file(ROOT / "frontend" / "site" / "index.html")
        if path in ("/client", "/client/"):
            return self._client_page()
        match = STATIC.fullmatch(path)
        if match:
            return self._file(ROOT / "frontend" / match.group(1) / match.group(2))
        if self.headers.get("X-Demo-Role") == "staff":
            match = re.fullmatch(r"/staff/cases/([^/]+)/candidates", path)
            if match and match.group(1) in mock_api.CASES:
                case = mock_api.CASES[match.group(1)]
                return self._send(200, {"candidates": STORE.rank_candidates(case["client_id"], case["categories"], V2)})
            match = re.fullmatch(r"/staff/cases/([^/]+)", path)
            if V2 and match and match.group(1) in mock_api.CASES:
                return self._send(200, with_v2_fields(mock_api.CASES[match.group(1)]))
        return super().do_GET()

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        turn = re.fullmatch(r"/intake/([^/]+)/turn", path)
        confirm = re.fullmatch(r"/intake/([^/]+)/confirm", path)
        if not ADAPTER or not (turn or confirm):
            return super().do_POST()
        if not self._role("client"):
            return
        body = self._body()
        if body is None:
            return self._error(400, "INVALID_JSON", "Send a JSON object.")
        session_id = (turn or confirm).group(1)
        session = mock_api.SESSIONS.get(session_id)
        if not session or self.headers.get("X-Demo-Client-Id") != session["client_id"]:
            return self._error(404, "SESSION_NOT_FOUND", "No authorized fictional session.")
        if turn:
            return self._adapter_turn(session_id, session, body)
        return self._adapter_confirm(session, body)

    def _adapter_turn(self, session_id: str, session: dict, body: dict):
        text, mode, option = body.get("text"), body.get("input_mode"), body.get("selected_option_id")
        if not isinstance(text, str) or mode not in ("text", "voice"):
            return self._error(400, "INVALID_TURN", "Send text and input_mode text or voice.")
        session.update(transcript=text, input_mode=mode)
        # Only the client's own choice of one of their accounts selects an account.
        if option and STORE.owns(session["client_id"], option):
            session["selected_account_id"] = option
        response = {
            "session_id": session_id, "transcript": text, "suggestions": [], "question": None,
            "definitions": [], "candidate_intent": session.get("candidate_intent"),
            "selected_account_id": session["selected_account_id"], "uncertainty": None,
        }
        try:
            result = ADAPTER.intake_turn(session["client_id"], text, option, STORE)
        except ADAPTER.BedrockAdapterError as error:
            # Keep the draft and let the client keep typing or ask for a person.
            response.update(question=error.message, status="needs_clarification",
                            uncertainty="The assistant could not be reached; the request was not interpreted.")
            return self._send(200, response)
        session["candidate_intent"] = result.get("candidate_intent")
        for key in ("suggestions", "question", "definitions", "candidate_intent", "uncertainty"):
            response[key] = result.get(key)
        ready = bool(session["selected_account_id"])
        if ready:
            response["suggestions"] = []
        response["status"] = "ready_for_client_review" if ready else "needs_clarification"
        self._send(200, response)

    def _adapter_confirm(self, session: dict, body: dict):
        client_id = session["client_id"]
        summary, account_id, amount = (body.get(k) for k in (
            "confirmed_plain_language_request", "selected_account_id", "amount_requested"))
        if not isinstance(summary, str) or not summary.strip():
            return self._error(400, "MISSING_CONFIRMATION", "Confirm the request in your own words.")
        if account_id and not STORE.owns(client_id, account_id):
            return self._error(400, "ACCOUNT_MISMATCH", "Account does not belong to this fictional client.")
        if amount is not None and (isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount < 0):
            return self._error(400, "INVALID_AMOUNT", "Enter the amount as a number, or leave it out.")
        try:
            triage = ADAPTER.triage_case({
                "confirmed_plain_language_request": summary, "original_words": session["transcript"],
                "candidate_intent": session.get("candidate_intent"), "selected_account_id": account_id,
                "amount_requested": amount,
            }, STORE)
        except ADAPTER.BedrockAdapterError as error:
            return self._error(503, error.code, "Your request was not sent. " + error.message)

        categories = triage["categories"]
        security = "fraud_or_security" in categories
        candidates = STORE.rank_candidates(client_id, categories)
        flags = list(triage["flags"])
        conflicts = STORE.wording_conflicts(client_id, session["transcript"], account_id)
        if conflicts and "client_term_did_not_match_account_type" not in flags:
            flags.append("client_term_did_not_match_account_type")  # verified against records, not guessed
        case_id = f"CASE-{mock_api.NEXT_CASE}"
        mock_api.NEXT_CASE += 1
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        mock_api.CASES[case_id] = {
            "case_id": case_id,
            "client_id": client_id,
            "client_display_name": STORE.client(client_id)["display_name"],
            "created_at": now,
            "client_confirmed_at": now,
            "status": "submitted",
            "input_mode": session.get("input_mode", "text"),
            "original_words": session["transcript"],
            "confirmed_plain_language_request": summary.strip(),
            "staff_summary": triage["staff_summary"],
            "intent": triage["intent"],
            "amount_requested": amount,
            "currency": "USD" if amount is not None else None,
            "selected_account_id": account_id,
            "account_match_status": "client_confirmed" if account_id else ("not_needed" if security else "unresolved"),
            "categories": categories,
            "unresolved_questions": triage["unresolved_questions"],
            "flags": flags,
            "account_context": STORE.account_context(account_id, categories),
            "routing": {
                "destination": "security_specialist_review" if security else (triage["routing_hint"] or "staff_review"),
                # Recommendations come from the directory rules, so an inactive or invented advisor cannot appear.
                "recommended_advisor_ids": [c["advisor_id"] for c in candidates if c["available"]][:2],
                "assigned_advisor_id": None,
                "staff_decision": None,
            },
        }
        self._send(200, {"case_id": case_id, "status": "submitted",
                         "client_summary": triage["client_summary"] or "Your request has been sent for staff review."})

    def _client_page(self):
        target = ROOT / "frontend" / "client" / "index.html"
        if not target.is_file():
            return self._error(404, "PATH_NOT_FOUND", "The client page is not in this checkout.")
        if self.path.split("?", 1)[0] == "/client":
            self.send_response(302)
            self.send_header("Location", "/client/")
            self.send_header("Content-Length", "0")
            return self.end_headers()
        html = target.read_text()
        if not (ADAPTER and ADAPTER.load_config().is_bedrock):
            html = html.replace("<head>", "<head><script>window.SAMEPAGE_MOCK_MODE=true;</script>", 1)
        self._bytes(html.encode(), "text/html; charset=utf-8")

    def _file(self, target: Path):
        if not target.is_file():
            return self._error(404, "PATH_NOT_FOUND", "No such file.")
        kind = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        text = kind.startswith("text") or target.suffix == ".js"
        self._bytes(target.read_bytes(), kind + ("; charset=utf-8" if text else ""))

    def _bytes(self, body: bytes, content_type: str):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
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
    parser.add_argument("--ai", choices=("preset", "adapter"), default="preset",
                        help="preset: mock_api answers. adapter: Agent 1's backend.aws adapter")
    args = parser.parse_args()
    V2 = args.v2
    mode = "preset answers; no AI"
    if args.ai == "adapter":
        try:
            import backend.aws as ADAPTER  # noqa: N811
        except ImportError as error:
            sys.exit(f"--ai adapter needs Agent 1's backend/aws package in this checkout ({error}).")
        mode = "LIVE Bedrock through Agent 1's adapter" if ADAPTER.load_config().is_bedrock \
            else "Agent 1's offline stub; no AI"
    print(f"Preview at http://127.0.0.1:{args.port}/staff ({mode}; fictional data)", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
