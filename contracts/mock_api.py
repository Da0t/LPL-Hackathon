"""Independent frontend mock for SamePage. Never use as the judged AI path."""

from __future__ import annotations

import copy
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


FIXTURE = json.loads((Path(__file__).parent / "demo_fixture_v1.json").read_text())
CASES = {case["case_id"]: copy.deepcopy(case) for case in FIXTURE["cases"]}
SESSIONS = {}
NEXT_SESSION = 1
NEXT_CASE = 1043


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: dict):
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers", "Content-Type, X-Demo-Role, X-Demo-Client-Id"
        )
        self.end_headers()
        self.wfile.write(encoded)

    def _error(self, status: int, code: str, message: str):
        self._send(status, {"error_code": code, "message": message})

    def _body(self):
        try:
            size = int(self.headers.get("Content-Length", "0"))
            return json.loads(self.rfile.read(size) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return None

    def _role(self, expected: str):
        if self.headers.get("X-Demo-Role") != expected:
            self._error(403, "WRONG_DEMO_ROLE", f"Use X-Demo-Role: {expected}.")
            return False
        return True

    def do_OPTIONS(self):
        self._send(200, {})

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if not self._role("staff"):
            return
        if path == "/staff/cases":
            rows = [
                {
                    key: case[key]
                    for key in (
                        "case_id", "client_display_name", "created_at", "status",
                        "categories", "flags", "confirmed_plain_language_request"
                    )
                }
                for case in CASES.values()
            ]
            self._send(200, {"cases": rows})
            return
        match = re.fullmatch(r"/staff/cases/([^/]+)/candidates", path)
        if match:
            case = CASES.get(match.group(1))
            if not case:
                self._error(404, "CASE_NOT_FOUND", "No such fictional case.")
                return
            if "fraud_or_security" in case["categories"]:
                self._send(200, {"candidates": []})
                return
            self._send(200, {"candidates": [
                {
                    "advisor_id": advisor["advisor_id"],
                    "display_name": advisor["display_name"],
                    "specialties": advisor["specialties"],
                    "available": advisor["available"],
                    "reason": "Retirement-income specialty and available for a new case."
                }
                for advisor in FIXTURE["advisors"]
                if advisor["advisor_id"] == "ADV-03"
            ]})
            return
        match = re.fullmatch(r"/staff/cases/([^/]+)", path)
        if match:
            case = CASES.get(match.group(1))
            if case:
                self._send(200, case)
            else:
                self._error(404, "CASE_NOT_FOUND", "No such fictional case.")
            return
        self._error(404, "PATH_NOT_FOUND", "No such endpoint.")

    def do_POST(self):
        global NEXT_SESSION, NEXT_CASE
        path = self.path.split("?", 1)[0]
        body = self._body()
        if body is None:
            self._error(400, "INVALID_JSON", "Send a JSON object.")
            return

        if path == "/intake/start":
            if not self._role("client"):
                return
            client_id = body.get("client_id")
            client = next((x for x in FIXTURE["clients"] if x["client_id"] == client_id), None)
            if not client or self.headers.get("X-Demo-Client-Id") != client_id:
                self._error(404, "CLIENT_NOT_FOUND", "No authorized fictional client.")
                return
            session_id = f"SESSION-{NEXT_SESSION:03d}"
            NEXT_SESSION += 1
            SESSIONS[session_id] = {"client_id": client_id, "transcript": "", "selected_account_id": None}
            self._send(200, {"session_id": session_id, "client_display_name": client["display_name"], "status": "draft"})
            return

        match = re.fullmatch(r"/intake/([^/]+)/turn", path)
        if match:
            if not self._role("client"):
                return
            session_id = match.group(1)
            session = SESSIONS.get(session_id)
            if not session or self.headers.get("X-Demo-Client-Id") != session["client_id"]:
                self._error(404, "SESSION_NOT_FOUND", "No authorized fictional session.")
                return
            transcript = body.get("text", "")
            if not isinstance(transcript, str) or body.get("input_mode") not in ("text", "voice"):
                self._error(400, "INVALID_TURN", "Send text and input_mode text or voice.")
                return
            session["transcript"] = transcript
            selected = body.get("selected_option_id")
            client_accounts = [a for a in FIXTURE["accounts"] if a["client_id"] == session["client_id"]]
            if any(a["account_id"] == selected for a in client_accounts):
                session["selected_account_id"] = selected
            ready = bool(session["selected_account_id"])
            ira_mismatch = session["client_id"] == "CLIENT-017" and "roth" in transcript.lower()
            self._send(200, {
                "session_id": session_id,
                "transcript": transcript,
                "suggestions": [] if ready else [
                    {"id": a["account_id"], "label": a["familiar_label"], "account_id": a["account_id"]}
                    for a in client_accounts[:3]
                ],
                "question": None if ready else (
                    "I don't see a Roth IRA here. Could you mean your rollover IRA from your former employer?"
                    if ira_mismatch else "Which of these accounts would you like to discuss?"
                ),
                "definitions": [{
                    "term": "rollover IRA", "plain": "A retirement account that holds money moved from an earlier workplace retirement plan."
                }] if ira_mismatch else [],
                "candidate_intent": "discuss_possible_withdrawal" if ira_mismatch else "account_service",
                "selected_account_id": session["selected_account_id"],
                "uncertainty": None if ready else (
                    "Client said Roth IRA; the authorized account list shows a rollover IRA instead."
                    if ira_mismatch else "The account has not been confirmed."
                ),
                "status": "ready_for_client_review" if ready else "needs_clarification"
            })
            return

        match = re.fullmatch(r"/intake/([^/]+)/confirm", path)
        if match:
            if not self._role("client"):
                return
            session = SESSIONS.get(match.group(1))
            if not session or self.headers.get("X-Demo-Client-Id") != session["client_id"]:
                self._error(404, "SESSION_NOT_FOUND", "No authorized fictional session.")
                return
            account_id = body.get("selected_account_id")
            account = next((a for a in FIXTURE["accounts"] if a["account_id"] == account_id), None)
            if account_id and (not account or account["client_id"] != session["client_id"]):
                self._error(400, "ACCOUNT_MISMATCH", "Account does not belong to this fictional client.")
                return
            summary = body.get("confirmed_plain_language_request")
            if not isinstance(summary, str) or not summary.strip():
                self._error(400, "MISSING_CONFIRMATION", "Confirm the request in your own words.")
                return
            case_id = f"CASE-{NEXT_CASE}"
            NEXT_CASE += 1
            case = copy.deepcopy(FIXTURE["cases"][0])
            client = next(x for x in FIXTURE["clients"] if x["client_id"] == session["client_id"])
            case.update({
                "case_id": case_id,
                "client_id": session["client_id"],
                "client_display_name": client["display_name"],
                "original_words": session["transcript"],
                "confirmed_plain_language_request": summary,
                "selected_account_id": account_id,
                "amount_requested": body.get("amount_requested"),
                "account_match_status": "client_confirmed" if account else "unresolved",
                "account_context": {
                    "account_type": account["account_type"],
                    "masked_identifier": account["masked_identifier"],
                    "balance": account["balance"],
                    "balance_as_of": account["balance_as_of"],
                    "account_source_id": account["source_id"],
                    "relevant_events": [
                        {"type": e["type"], "date": e["date"], "source_id": e["source_id"]}
                        for e in FIXTURE["events"] if e["account_id"] == account_id
                    ]
                } if account else None,
                "status": "submitted"
            })
            if session["client_id"] != "CLIENT-017" or account_id != "ACCT-201":
                case["staff_summary"] = "Fictional request ready for staff review."
                case["categories"] = ["other_or_unclear"]
                case["flags"] = []
                case["routing"] = {
                    "destination": "staff_review", "recommended_advisor_ids": [],
                    "assigned_advisor_id": None, "staff_decision": None
                }
            CASES[case_id] = case
            self._send(200, {"case_id": case_id, "status": "submitted", "client_summary": "Your request has been sent for staff review."})
            return

        match = re.fullmatch(r"/staff/cases/([^/]+)/assign", path)
        if match:
            if not self._role("staff"):
                return
            case = CASES.get(match.group(1))
            advisor_id = body.get("advisor_id")
            advisor = next((a for a in FIXTURE["advisors"] if a["advisor_id"] == advisor_id), None)
            if not case or not advisor or not body.get("staff_reason"):
                self._error(400, "INVALID_ASSIGNMENT", "Case, advisor, and staff reason are required.")
                return
            if "fraud_or_security" in case["categories"]:
                self._error(400, "SPECIALIST_REVIEW", "This fictional case needs specialist review.")
                return
            case["status"] = "assigned"
            case["routing"]["assigned_advisor_id"] = advisor_id
            case["routing"]["staff_decision"] = body["staff_reason"]
            self._send(200, {"case_id": case["case_id"], "status": "assigned", "assigned_advisor_id": advisor_id})
            return

        self._error(404, "PATH_NOT_FOUND", "No such endpoint.")


if __name__ == "__main__":
    print("SamePage mock API at http://localhost:8001 (fictional data; no AI)")
    ThreadingHTTPServer(("127.0.0.1", 8001), Handler).serve_forever()
