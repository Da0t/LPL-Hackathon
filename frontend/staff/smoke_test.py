"""Browser check for the staff page against the local preview server.

Needs Playwright (pip install playwright; python3 -m playwright install chromium).
It is a development check, not part of the app's requirements. When the client page is
also being served, the request is typed into it; otherwise it is posted to the API.

Run from the repository root:

    python3 frontend/staff/smoke_test.py
    python3 frontend/staff/smoke_test.py --screenshots frontend/staff/screenshots

To check the page against the real backend instead, start the app and pass its address:

    python3 frontend/staff/smoke_test.py --base http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
REQUEST = "I need six thousand dollars from the Roth thing from my old job."
CONFIRMED = "I want to speak with an advisor about using $6,000 from my retirement account from my former employer."
RESULTS = []


def check(name: str, ok: bool, detail: str = ""):
    RESULTS.append(ok)
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail and not ok else ""))


def client_post(base: str, path: str, body: dict) -> dict:
    request = urllib.request.Request(base + path, json.dumps(body).encode(), {
        "Content-Type": "application/json", "X-Demo-Role": "client", "X-Demo-Client-Id": "CLIENT-017",
    })
    return json.load(urllib.request.urlopen(request, timeout=60))


def submit_case(base: str) -> str:
    session = client_post(base, "/intake/start", {"client_id": "CLIENT-017"})["session_id"]
    client_post(base, f"/intake/{session}/turn", {"text": REQUEST, "input_mode": "text", "selected_option_id": None})
    time.sleep(1.1)  # stay under the one-call-per-second Bedrock limit on the real backend
    client_post(base, f"/intake/{session}/turn", {"text": REQUEST, "input_mode": "text", "selected_option_id": "ACCT-201"})
    time.sleep(1.1)
    return client_post(base, f"/intake/{session}/confirm", {
        "confirmed_plain_language_request": CONFIRMED, "selected_account_id": "ACCT-201", "amount_requested": 6000,
    })["case_id"]


def submit_through_client_page(page, base: str) -> str:
    """Type the request into the client page, as the presenter will."""
    page.goto(base + "/client/")
    page.click("#start")
    page.wait_for_selector("#words", state="visible")
    page.fill("#words", REQUEST)
    page.wait_for_selector(".suggestion-card", timeout=30000)
    page.locator(".suggestion-card").first.click()
    page.click("#review")
    page.wait_for_selector("#summary", state="visible")
    page.fill("#summary", CONFIRMED)
    page.fill("#amount", "6,000")
    page.click("#confirm")
    page.wait_for_selector("#success-screen", state="visible", timeout=30000)
    return re.search(r"CASE-[\w-]+", page.inner_text("#success-screen")).group(0)


def has_client_page(base: str) -> bool:
    try:
        return urllib.request.urlopen(base + "/client/", timeout=10).status == 200
    except OSError:
        return False


def run(base: str, shots: Path | None, preview: bool):
    def shot(page, name, **kwargs):
        if shots:
            page.screenshot(path=str(shots / name), **kwargs)

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            browser = p.chromium.launch(channel="chrome")
        # Tall when taking screenshots so the whole case is captured; a laptop size otherwise.
        page = browser.new_page(viewport={"width": 1440, "height": 1500 if shots else 900})
        page_errors = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))

        page.goto(base + "/staff")
        page.wait_for_selector(".case-row")
        check("queue lists the seed cases", page.locator(".case-row:has-text('CASE-1042')").count() == 1
              and page.locator(".case-row:has-text('CASE-SEC-1')").count() == 1)
        check("bundled fonts load", page.evaluate(
            "Promise.all([document.fonts.load('16px Inter'), document.fonts.load('italic 16px Newsreader')])"
            ".then(loaded => loaded.every(faces => faces.length > 0))"))
        shot(page, "1-queue.png")

        if has_client_page(base):
            client_page = browser.new_page(viewport={"width": 1280, "height": 900})
            client_page.on("pageerror", lambda error: page_errors.append("client page: " + str(error)))
            case_id = submit_through_client_page(client_page, base)
            check("the client page submits a request and shows its case number", bool(case_id))
            client_page.close()
        else:
            case_id = submit_case(base)
        page.wait_for_selector(f".case-row:has-text('{case_id}')", timeout=9000)
        check("a newly confirmed case appears without a reload", True)

        page.click(f".case-row:has-text('{case_id}')")
        page.wait_for_selector(".candidate")
        text = page.inner_text("#case")
        check("case shows the client's original words", REQUEST in text)
        check("case shows the confirmed request", CONFIRMED in text)
        check("case shows masked account, as-of date, and sources",
              "****4821" in text and "as of" in text and "ACCOUNT-RECORD-201" in text and "EVENT-09" in text)
        check("mismatch notice is shown", page.locator(".mismatch").count() == 1)
        advisors = page.locator(".candidate input[value^='ADV']").count()
        check("one to three advisor candidates", 1 <= advisors <= 3, str(advisors))
        check("ADV-03 is a candidate with a reason", page.locator(".candidate:has(input[value='ADV-03'])").count() == 1)
        check("assign is disabled before a choice", page.is_disabled("button.primary"))
        shot(page, "2-case.png", full_page=True)

        page.check("input[value='ADV-03']")
        check("assign is disabled without a reason", page.is_disabled("button.primary"))
        page.fill("#staff-reason", "Retirement-income specialty, available, offers phone meetings.")
        page.click("button.primary")
        page.wait_for_selector(".notice.ok")
        check("assignment is confirmed on the case", "ADV-03" in page.inner_text(".notice.ok"))
        page.wait_for_selector(f".case-row:has-text('{case_id}') .tag.status.assigned")
        check("queue row shows assigned", True)
        shot(page, "3-assigned.png", full_page=True)

        page.click(".case-row:has-text('CASE-SEC-1')")
        page.wait_for_selector(".security-banner")
        check("security case shows specialist review and no assignment form",
              page.locator("#case form").count() == 0 and "specialist" in page.inner_text(".security-banner").lower())
        shot(page, "4-security.png", full_page=True)

        if preview:  # these rely on seed case CASE-1041 and on rewriting responses
            page.click(".case-row:has-text('CASE-1041')")
            page.wait_for_selector(".candidate")
            page.fill("#other-advisor", "ADV-99")
            page.fill("#staff-reason", "Testing an unknown advisor.")
            page.click("button.primary")
            page.wait_for_selector(".notice.error")
            check("a rejected assignment leaves the status unchanged",
                  page.inner_text(".case-meta .tag.status") != "Assigned")

        page.keyboard.press("j")
        check("J moves to the next request", page.locator(".case-row[aria-current='true']").count() == 1)
        page.fill("#search", "sign-in")
        check("search narrows the queue", page.locator(".case-row").count() == 1)
        page.fill("#search", "")

        page.set_viewport_size({"width": 390, "height": 800})
        page.click(".case-row:has-text('CASE-1042')")
        page.wait_for_selector(".case-head")
        check("no sideways scrolling at phone width", not page.evaluate("document.documentElement.scrollWidth > innerWidth"))
        shot(page, "5-phone.png", full_page=True)

        page.route("**/staff/cases", lambda route: route.fulfill(json={"cases": []}))
        page.click("#refresh")
        page.wait_for_function("document.getElementById('queue-status').textContent.includes('No requests are waiting')")
        check("empty queue explains itself", True)
        page.unroute("**/staff/cases")
        page.route("**/staff/cases", lambda route: route.abort())
        page.click("#refresh")
        page.wait_for_function("document.getElementById('queue-status').textContent.includes(\"Can't reach\")")
        check("unreachable service explains itself", True)

        check("no script errors", not page_errors, "; ".join(page_errors))
        browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", help="address of a running app; default starts the preview server")
    parser.add_argument("--v2", action="store_true", help="start the preview with the proposed v2 fields")
    parser.add_argument("--ai", choices=("preset", "adapter"), default="preset",
                        help="start the preview with Agent 1's adapter (needs backend/aws in the checkout)")
    parser.add_argument("--screenshots", type=Path, help="folder to save screenshots in")
    args = parser.parse_args()
    if args.screenshots:
        args.screenshots.mkdir(parents=True, exist_ok=True)

    server = None
    base = args.base
    if not base:
        port = 8011
        command = [sys.executable, str(ROOT / "frontend/staff/dev_server.py"), "--port", str(port)]
        command += ["--ai", args.ai] + (["--v2"] if args.v2 else [])
        server = subprocess.Popen(command, stdout=subprocess.PIPE, text=True)
        server.stdout.readline()  # wait for the startup line
        base = f"http://127.0.0.1:{port}"
    try:
        run(base.rstrip("/"), args.screenshots, preview=server is not None)
    finally:
        if server:
            server.terminate()
    print(f"{sum(RESULTS)} of {len(RESULTS)} checks passed")
    sys.exit(0 if all(RESULTS) else 1)
