# SamePage five-minute demo script

Everything shown is fictional: Mara Ellis, her accounts, the balances, and every advisor. This is the speaking and clicking plan. The judged deck still has to be built in the LPL PowerPoint template.

The spoken lines below total about 440 words. At a calm 150 words a minute that is about three minutes of talking, which leaves about two minutes for the app to respond, typing, and clicks. Rehearse with a timer; the cut list at the end says what to drop if you run long.

## Before you present

1. Run `python -m backend.reset_demo` (Agent 2's command), then start the app as described in `INTEGRATION_RUNBOOK.md` with `SAMEPAGE_AI_MODE=bedrock`.
2. Open two tabs side by side: `http://127.0.0.1:8000/client` and `http://127.0.0.1:8000/staff`. Zoom both to about 125%.
3. On the client tab, choose fictional client `CLIENT-017` (Mara Ellis).
4. On the staff tab, confirm the queue shows `CASE-1042` and `CASE-SEC-1`, and that `CASE-1042` is not assigned.
5. Test the microphone once. If it is unreliable, type the request. Never switch the judged path to the mock API.
6. Keep the backup recording and the screenshots in `frontend/staff/screenshots/` open in a third tab.

Roles: one person speaks, one clicks, one watches the clock and calls the cuts.

## 0:00 Problem (40 seconds, slide)

> Clients know their life problem. They don't know the financial term for it.
>
> Meet Mara. Her husband needs care, and she needs six thousand dollars. She calls her account "the Roth thing from my old job." She doesn't have a Roth.
>
> If someone simply writes down what she said, an advisor receives a request about an account that doesn't exist. Then Mara has to explain herself all over again, to someone new.

## 0:40 Product (15 seconds, slide, then switch to the client tab)

> SamePage turns everyday words into a confirmed request, checked against the client's own accounts, and hands staff a case they can trust.

## 0:55 Client demo (2 minutes, live)

| Do | Say |
| --- | --- |
| Speak or type: **"I need six thousand dollars from the Roth thing from my old job."** | Mara is signed in. She just says what she needs. |
| Wait for the question and suggestions. | Our agent, running on Amazon Bedrock, looked up her accounts. It did not guess. It says: I don't see a Roth IRA here. Could you mean your rollover IRA from your former employer? |
| Open the "rollover IRA" definition. | She can ask what that means. The answer is plain language from an approved glossary, not improvised advice. |
| Select the former-employer retirement account. Open the review page. **Check the "What we understood" text.** If it still shows her raw words, edit it to: *I want to speak with an advisor about using $6,000 from my retirement account from my former employer.* Enter the amount **6,000** if it is empty. | She picks the retirement account from her old job and reviews the request in her own words. The amount is there only because she said it and confirmed it. |
| Click **Confirm and send request**. Read the case number aloud. | She confirms. Nothing is sent without that. This is her case number. |

## 2:55 Staff demo (1 minute, live, staff tab)

| Do | Say |
| --- | --- |
| Point at the new case at the top of the queue. Open it. | This is the staff queue. The same case just arrived. Nobody retyped it. |
| Point at the quote, then the yellow notice. | Here are her exact words, and what she confirmed. And here is the catch: her wording did not match her records. That was settled with Mara before any advisor saw it. |
| Scroll to page 2. Point at the source labels. | Page two shows only the account that matters: a masked number, a balance with its date, and the rollover that explains why she called it the account from her old job. Every fact shows its source. |
| Choose Jordan Lee. Type **"Retirement-income specialty, available, offers phone meetings."** Click **Assign case**. (If typing is slow, **Use suggested reason** fills the box with the system's reason for you to accept or edit.) | The system suggests advisors and says why. A person decides, and records the reason. |
| Open `CASE-SEC-1`. Show the red banner. | And a client who reports a strange sign-in goes to security specialists, never to a planning advisor. |

## 3:55 Why LPL buys it (25 seconds, slide)

> LPL connects investors with about thirty-two thousand advisors. SamePage is the layer between them: a plain-language vocabulary, clarification grounded in real accounts, client confirmation, and routing a human approves.
>
> Buying it is faster than building that handoff from a blank page. That is our proposal, not a claim about LPL's roadmap.

## 4:20 AWS (20 seconds, slide)

> Amazon Bedrock, in us-east-1, interprets the request and classifies the case, using a model from the approved list. Our own code handles account lookup, validation, and routing, so the model never invents an account fact. No hard-coded keys. Synthetic data only.

State accurately how voice input works in the build you are showing (Amazon Transcribe, browser speech recognition, or typed only).

## 4:40 Impact and close (20 seconds, slide)

> In a pilot we would measure three things: time from first request to the right destination, contacts needed to clarify a request, and how often staff override the suggestion.
>
> SamePage lets clients speak in their own words and gives advisors a request they can trust.

## If you are running long

Cut in this order. Each saves about ten seconds.

1. The glossary definition in the client demo.
2. Opening `CASE-SEC-1`. Say the security sentence over the queue, where the red row is already visible.
3. The second sentence of the AWS section.

Never cut the client confirming, the mismatch notice, or the manual assignment. Those three are the product.

## What is live and what is simulated

Keep this on a slide and say it if asked.

- **Live:** Bedrock interpretation and triage, case creation, the staff queue, and assignment.
- **Simulated:** sign-in (a demo role switcher), every client, account, balance, event, and advisor, and advisor notification (nothing is sent).
- **Not measured:** time saved or retention. The three pilot measures are proposed, not results.

## Reset between runs

1. Stop the server if Agent 2's reset requires it.
2. Run `python -m backend.reset_demo`. New cases and assignments are cleared.
3. Reload both tabs. The staff queue should show only the seed cases, with `CASE-1042` unassigned.

## If something fails

- **Microphone fails:** type the same sentence. The typed path is the same flow.
- **Bedrock is slow or throttled:** wait a second and resend once. If it still fails, say the live call did not return and narrate the staff side with seed case `CASE-1042`, which holds the same scenario.
- **Staff queue does not update:** click **Refresh**. The page also checks for new cases every five seconds.
- **App will not start:** play the backup recording and say so.

## Likely questions

- **Why an agent and not a form?** A form needs the client to already know the term. The agent starts from their words and checks them against their accounts.
- **What stops the model inventing an account?** It can only suggest accounts returned by the backend's lookup, the client must confirm, and staff see the source of every account fact.
- **Is this advice?** No. It creates and routes a service request. It does not recommend or execute anything.
- **What would production need?** Real authentication, the firm's advisor directory with verified licence and state eligibility, audit logging, and review of the glossary by compliance.

## Contingency: if the backend is not ready

As of the evening of October 2, Agent 2's backend was not on the remote. If `backend/main.py` is still missing when you rehearse, the preview server can stand in. It serves both pages and the version-one API on one origin and sends intake and triage through Agent 1's adapter, so the AI path is still live Bedrock.

After merging the Agent 1, Agent 3, and Agent 4 branches:

```bash
pip install -r requirements-aws.txt
export AWS_REGION=us-east-1 BEDROCK_MODEL_ID=<verified allowlisted model ID> SAMEPAGE_AI_MODE=bedrock
python3 frontend/staff/dev_server.py --ai adapter --port 8000
```

Open `http://127.0.0.1:8000/client` and `http://127.0.0.1:8000/staff`. The startup line says whether it is using live Bedrock or the offline stub; only live Bedrock may be shown as the AI demo. Cases are kept in memory, so **restarting the server is the reset**. This path was tested end to end with Agent 1's offline stub. It has not been run against live Bedrock, because that needs the event account.

Be accurate in the pitch if you use it: it is a single-process prototype server with in-memory cases, not the FastAPI backend in the architecture slide.

## The SamePage site

`frontend/site/` is a scroll-driven page that tells the same story as the pitch: the client's sentence, the check against her accounts, her confirmation, and the handoff to staff, followed by the four scenarios. It can stand behind the problem and product parts of the talk instead of slides, or serve as the page to leave on screen during questions. It links to `/client` and `/staff`. The preview server serves it at `/site/`; in the integrated app, mount the folder at `/site`.

## Staff page preview without the backend

`python3 frontend/staff/dev_server.py`, then open `http://127.0.0.1:8001/staff`. This reuses `contracts/mock_api.py` with the expanded `data/` files and returns preset answers. It is for development and backup screenshots only, never the judged demo. `python3 frontend/staff/smoke_test.py` checks the page in a browser; add `--base http://127.0.0.1:8000` to run the same check against the integrated app.
