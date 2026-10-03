# SamePage five-minute demo script

Everything shown is fictional: Mara Ellis, her accounts, the balances, and every advisor. This script is the speaking and clicking plan; the judged deck still has to be built in the LPL PowerPoint template.

## Before you present

1. `python -m backend.reset_demo` (Agent 2's command), then start the app as described in `INTEGRATION_RUNBOOK.md` with `SAMEPAGE_AI_MODE=bedrock`.
2. Open two browser tabs side by side: `http://127.0.0.1:8000/client` and `http://127.0.0.1:8000/staff`. Zoom both to about 125%.
3. On the client tab, choose fictional client `CLIENT-017` (Mara Ellis).
4. On the staff tab, confirm the queue shows `CASE-1042` and `CASE-SEC-1`.
5. Test the microphone once. If it is unreliable, type the request. Never switch the judged path to the mock API.
6. Keep the backup recording and screenshots open in a third tab.

Roles: one person speaks, one clicks, one watches the clock.

## The script

| Time | Speaker says | On screen |
| --- | --- | --- |
| 0:00 to 0:40 **Problem** | "Clients know their life problem, not the financial term for it. Mara needs money for her husband's care. She calls it 'the Roth thing from my old job.' She doesn't have a Roth. If someone writes down what she said, an advisor gets a request about an account that doesn't exist, and Mara explains herself all over again." | Problem slide |
| 0:40 to 1:00 **Product** | "SamePage turns everyday words into a confirmed request, checked against the client's own accounts, and hands staff a case they can trust." | Product slide, then switch to the client tab |
| 1:00 to 3:00 **Client demo** | "Mara is signed in. She just says what she needs." Speak or type: **"I need six thousand dollars from the Roth thing from my old job."** | Client page: transcript appears |
| | "The agent, running on Amazon Bedrock, looked at her accounts. It did not guess. It says: I don't see a Roth IRA. Could you mean your rollover IRA from your former employer?" | Clarifying question and up to three suggestions |
| | "She can ask what that term means, in plain language, from an approved glossary." | Open the "rollover IRA" definition |
| | "She picks the retirement account from her former job, and reviews the request in her own words. The amount is there only because she said it and confirmed it." | Select the account, show the review page |
| | "She confirms. Nothing is sent without that." Read the case number aloud. | Click **Confirm and send request**; note the case ID |
| 3:00 to 4:00 **Staff demo** | "Here is the staff queue. That same case just arrived. Nobody retyped it." | Staff tab: the new case highlights at the top |
| | "Page one: her exact words, and what she confirmed. And here is the catch: her wording did not match her records. The mismatch was resolved with the client before any advisor saw it." | Open the case; point at the quote and the yellow notice |
| | "Page two: only the account that matters. Masked number, a balance with its as-of date, and the 2023 rollover that explains why she called it the account from her old job. Every fact shows its source." | Scroll to page 2; point at the source labels |
| | "The system suggests up to three advisors and says why. A person decides." Choose Jordan Lee, type the reason **"Retirement-income specialty, available, offers phone meetings."** | Click **Assign case**; status changes to Assigned |
| | "And when a client reports a sign-in they don't recognize, it goes to security specialists, never to a planning advisor." | Open `CASE-SEC-1`; show the red banner |
| 4:00 to 4:25 **Why LPL buys it** | "LPL connects investors with about 32,500 advisors. SamePage is the layer between them: plain-language vocabulary, account-grounded clarification, client confirmation, and human-approved routing. Buying it is faster than building that handoff from scratch. That is our proposal, not a claim about LPL's roadmap." | Acquisition slide |
| 4:25 to 4:45 **AWS** | "Amazon Bedrock, in us-east-1, interprets the request and classifies the case, using an allowlisted model. Our own code handles account lookup, validation, and routing, so the model never invents an account fact. No hard-coded keys, synthetic data only." State accurately how voice input works in the build you are showing. | Architecture slide |
| 4:45 to 5:00 **Impact and close** | "In a pilot we would measure three things: time from first request to the right destination, contacts needed to clarify a request, and how often staff override the suggestion. SamePage lets clients speak in their own words and gives advisors a request they can trust." | Impact slide |

## What is live and what is simulated

Say this if asked, and keep it on a slide:

- **Live:** Bedrock interpretation and triage, case creation, the staff queue, and assignment.
- **Simulated:** sign-in (a demo role switcher), every client, account, balance, event, and advisor, and advisor notification (nothing is sent).
- **Not measured:** time saved or retention. The three pilot measures are proposed, not results.

## Reset between runs

1. Stop the server if Agent 2's reset requires it.
2. Run `python -m backend.reset_demo`. New cases and assignments are cleared.
3. Reload both tabs. The staff queue should again show only the seed cases, with `CASE-1042` unassigned.

## If something fails

- **Microphone fails:** type the same sentence. The typed path is the same flow.
- **Bedrock is slow or throttled:** wait a second and resend once. Narrate the staff side using seed case `CASE-1042`, which shows the same scenario, and say the live call did not return.
- **Staff queue does not update:** click **Refresh**. The page also checks for new cases every five seconds.
- **App will not start:** play the backup recording and say so.

## Staff page preview without the backend

`python3 frontend/staff/dev_server.py`, then open `http://127.0.0.1:8001/staff`. This uses `contracts/mock_api.py` with the expanded `data/` files and returns preset answers. It is for development and backup screenshots only, never the judged demo.
