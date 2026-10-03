"""Generate docs/API_EXAMPLES.md from a real run of the backend in mock mode.

    python scripts/generate_api_examples.py

Agents 3 and 4 can build against these exact response shapes. Re-run after any
contract change so the document never drifts from the implementation.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import create_app  # noqa: E402
from backend.settings import REPO_ROOT, Settings  # noqa: E402

STAFF = {"X-Demo-Role": "staff"}
CLIENT = {"X-Demo-Role": "client"}
ROTH_THING = "I need six thousand dollars for my husband's care. It's in the Roth thing from my old job."
SECURITY = "Someone moved money out of my brokerage account and I didn't do it."

OUT = ROOT / "docs" / "API_EXAMPLES.md"


def block(title: str, method: str, path: str, request_body, response, headers: dict[str, str] | None = None, note: str | None = None) -> str:
    lines = [f"### {title}", ""]
    header_note = f" with header `X-Demo-Role: {headers['X-Demo-Role']}`" if headers else ""
    lines.append(f"`{method} {path}`{header_note}")
    lines.append("")
    if note:
        lines.append(note)
        lines.append("")
    if request_body is not None:
        lines += ["Request:", "", "```json", json.dumps(request_body, indent=2), "```", ""]
    lines += [f"Response ({response.status_code}):", "", "```json", json.dumps(response.json(), indent=2), "```", ""]
    return "\n".join(lines)


def main() -> None:
    tmp = Path(tempfile.mkdtemp())
    settings = Settings(
        agent_mode="mock", db_path=":memory:", data_dir=REPO_ROOT / "data",
        fallback_data_dir=REPO_ROOT / "backend" / "fixtures", default_demo_role="client",
        adapter_timeout_s=10.0, client_frontend_dir=tmp / "client", staff_frontend_dir=tmp / "staff",
    )
    sections: list[str] = []
    with TestClient(create_app(settings)) as c:
        sections.append(block("Health (additive)", "GET", "/health", None, c.get("/health")))
        sections.append(block("Demo clients for the role switcher (additive)", "GET", "/demo/clients", None, c.get("/demo/clients")))

        body = {"client_id": "CLIENT-017"}
        r = c.post("/intake/start", json=body, headers=CLIENT)
        sid = r.json()["session_id"]
        sections.append(block("Start an intake session", "POST", "/intake/start", body, r, CLIENT))

        body = {"text": ROTH_THING, "input_mode": "voice"}
        r = c.post(f"/intake/{sid}/turn", json=body, headers=CLIENT)
        sections.append(block("Turn 1: ambiguous request, agent asks instead of guessing", "POST", f"/intake/{{session_id}}/turn", body, r, CLIENT,
                              "`selected_account_id` stays null: the rollover IRA is only a proposal until the client picks it. `candidate_account_id` and `proposed_plain_language_request` are additive fields."))
        yes_id = next(s["id"] for s in r.json()["suggestions"] if s["account_id"] == "ACCT-201")

        body = {"text": "", "input_mode": "text", "selected_option_id": yes_id}
        r = c.post(f"/intake/{sid}/turn", json=body, headers=CLIENT)
        sections.append(block("Turn 2: client picks a suggestion card", "POST", f"/intake/{{session_id}}/turn", body, r, CLIENT,
                              "Empty `text` keeps the saved transcript. The chosen card's account becomes `selected_account_id`."))

        body = {"text": "", "input_mode": "text", "selected_option_id": "opt-withdraw"}
        r = c.post(f"/intake/{sid}/turn", json=body, headers=CLIENT)
        sections.append(block("Turn 3: ready for client review", "POST", f"/intake/{{session_id}}/turn", body, r, CLIENT,
                              "No `question` means the review screen can open. Show `proposed_plain_language_request` in \"What we understood\" and let the client edit it."))
        proposed = r.json()["proposed_plain_language_request"]

        body = {"confirmed_plain_language_request": proposed, "selected_account_id": "ACCT-201", "amount_requested": 6000}
        r = c.post(f"/intake/{sid}/confirm", json=body, headers=CLIENT)
        case_id = r.json()["case_id"]
        sections.append(block("Confirm and send request", "POST", f"/intake/{{session_id}}/confirm", body, r, CLIENT,
                              "Only values in this body count as confirmed. An amount the client said but did not confirm is never inferred."))

        # Second case: security routing.
        sid2 = c.post("/intake/start", json={"client_id": "CLIENT-031"}, headers=CLIENT).json()["session_id"]
        t = c.post(f"/intake/{sid2}/turn", json={"text": SECURITY, "input_mode": "text"}, headers=CLIENT).json()
        sec = c.post(f"/intake/{sid2}/confirm", json={"confirmed_plain_language_request": t["proposed_plain_language_request"], "selected_account_id": "ACCT-222"}, headers=CLIENT).json()

        sections.append(block("Staff queue", "GET", "/staff/cases", None, c.get("/staff/cases", headers=STAFF), STAFF,
                              "Optional filters: `?status=submitted` and `?category=fraud_or_security`. Fields after `confirmed_plain_language_request` are additive."))
        sections.append(block("Case document (two-page equivalent)", "GET", "/staff/cases/{case_id}", None, c.get(f"/staff/cases/{case_id}", headers=STAFF), STAFF,
                              "Opening a `submitted` case moves it to `staff_review`. `account_context` comes only from records with source ids; `conversation` and `history` are additive."))
        sections.append(block("Advisor candidates", "GET", "/staff/cases/{case_id}/candidates", None, c.get(f"/staff/cases/{case_id}/candidates", headers=STAFF), STAFF,
                              "At most three. The existing active advisor is first; `eligibility_check` is always `manual_verification_required`."))
        body = {"advisor_id": "ADV-01", "staff_reason": "Existing advisor with retirement and distribution specialty; available this week."}
        sections.append(block("Assign (human decision)", "POST", "/staff/cases/{case_id}/assign", body, c.post(f"/staff/cases/{case_id}/assign", json=body, headers=STAFF), STAFF,
                              "No message, transaction, or appointment is created. The reason is recorded in the case history."))
        sections.append(block("Security case candidates route to the specialist queue", "GET", "/staff/cases/{case_id}/candidates", None,
                              c.get(f"/staff/cases/{sec['case_id']}/candidates", headers=STAFF), STAFF))

        # Errors
        sections.append(block("Error: staff endpoint without the staff role", "GET", "/staff/cases", None, c.get("/staff/cases"), None))
        sections.append(block("Error: option id not shown on the last turn", "POST", "/intake/{session_id}/turn", {"text": "", "selected_option_id": "opt-99"},
                              c.post(f"/intake/{sid2}/turn", json={"text": "", "selected_option_id": "opt-99"}, headers=CLIENT), CLIENT))
        other_sid = _fresh_session_with_turn(c)
        body = {"confirmed_plain_language_request": "Money from my Roth IRA", "selected_account_id": "ACCT-211"}
        sections.append(block("Error: another client's account", "POST", "/intake/{session_id}/confirm", body,
                              c.post(f"/intake/{other_sid}/confirm", json=body, headers=CLIENT), CLIENT))

    intro = f"""# SamePage API examples (generated)

Generated by `python scripts/generate_api_examples.py` from a real run of the backend in
**mock** mode against the fallback fixtures. Every value is synthetic. Field names are the
frozen version-one contract from `SAMEPAGE_PRODUCT_SPEC.md`; fields noted as *additive*
are extra and safe to ignore.

Conventions:

- Base URL `http://127.0.0.1:8000`. Pages: `/client`, `/staff`. Interactive docs: `/docs`.
- Demo role switcher (simulated access control, not authentication): header `X-Demo-Role: client`
  for `/intake/*`, `X-Demo-Role: staff` for `/staff/*` and `/demo/reset`. Missing header = `client`.
- `text` in a turn is the **whole editable transcript** so far. Send `""` with a `selected_option_id`
  for a selection-only turn. Reserved option ids: `none_of_these`, `talk_to_person`.
- Errors are `{{"error_code", "message"}}` (plus `details` when useful).

"""
    OUT.write_text(intro + "\n".join(sections), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


def _fresh_session_with_turn(c: TestClient) -> str:
    sid = c.post("/intake/start", json={"client_id": "CLIENT-017"}, headers=CLIENT).json()["session_id"]
    c.post(f"/intake/{sid}/turn", json={"text": "money from my roth from my old job"}, headers=CLIENT)
    return sid


if __name__ == "__main__":
    main()
