# Coherent five-minute demo script

Everything shown is fictional: Mara Ellis, her accounts, the balances, and every advisor. This is the speaking and clicking plan. The judged deck still has to be built in the LPL PowerPoint template.

The spoken lines below total about 450 words. At a calm 150 words a minute that is three minutes of talking, which leaves two minutes for the app to respond, typing, and clicks. Rehearse with a timer; the cut list at the end says what to drop if you run long.

**Status of this script:** the screen names, button labels, and order below were taken from the current code. The full click path has not been walked in a browser since the client portal and the prepared action packet were merged, so rehearse it once end to end and correct any label that differs.

## Before you present

1. Start the backend and frontend as described in `README.md`, with `COHERENT_PORTAL_CONFIG` set and `SAMEPAGE_AI_MODE=bedrock`. Open `http://127.0.0.1:8000/health` and check it says `"ai_mode":"bedrock"`. If it says `mock`, you are not showing the judged path.
2. Run `python -m backend.reset_demo`. The server does not need a restart.
3. Sign-in is a browser cookie, so the client and the advisor cannot share one browser session. Open `http://127.0.0.1:3200/login` in **two separate windows**: a normal window signed in as Mara Ellis, and a private window (or second browser profile) signed in as staff. The demo sign-ins are in `var/demo-access.json`. Zoom both to about 125%.
4. Client window: open **New request** (`/workspace/requests/new`). Advisor window: open `/dashboard` and confirm the queue shows `CASE-1042` and `CASE-SEC-1`, with the security case at the top.
5. Test the microphone once. If it is unreliable, type the request.
6. **Rehearse the reply beat on live Bedrock at least twice.** See "The reply beat on live Bedrock" below.
7. Cognito sessions expire after one hour. Sign in again in both windows shortly before you present.
8. Keep the backup recording open in a third tab.

Roles: one person speaks, one clicks, one watches the clock and calls the cuts.

## 0:00 Problem (35 seconds, slide)

> Clients know their life problem. They don't know the financial term for it.
>
> Meet Mara. Her husband needs care, and she needs six thousand dollars. She calls her account "the Roth thing from my old job." She doesn't have a Roth.
>
> If someone writes down what she said, an advisor gets a request about an account that doesn't exist, and Mara explains herself again to someone new.

## 0:35 Product (10 seconds, slide, then switch to the client window)

> Coherent turns everyday words into a confirmed request, checked against the client's own accounts, and hands the advisor a case they can act on.

## 0:45 Client demo (1 minute 30, live, client window)

The request editor has three columns: her words, the clarification, and the request document.

| Do | Say |
| --- | --- |
| In **Your request**, speak or type: **"I need six thousand dollars from the Roth thing from my old job."** Click **Clarify my request**. | Mara is signed in. She just says what she needs. |
| Wait for the question and suggestions in the middle column. | Bedrock looked up her accounts. It did not guess. It says: I don't see a Roth IRA here. Could you mean your rollover IRA from your former employer? |
| Pick the rollover IRA suggestion, then the option to discuss taking money out. | One question at a time, and every option comes from her real records. |
| Point at the document in the right column: description, **Account to discuss**, amount **6000**. | This is the exact document her team will receive, in plain words, with her real account and its history. |
| Click **Confirm and send request**. | She confirms. Nothing is sent without that. |

## 2:15 Advisor demo (1 minute 40, live, advisor window)

| Do | Say |
| --- | --- |
| Reload. Point at the red row at the top, then open Mara's new case. | The queue ranks itself and says why. A possible security issue goes to specialists first, never to a planning advisor. Here is Mara. |
| Point at the header line **Intake took 3 turns** and the **Reply ready for your review** card. | Three turns, under a minute. And the advisor does not open a transcript. The agents have already gathered the facts, run the compliance checks, and drafted the next step. |
| Point at **What the client asked** and the amber notice. | Her exact words, what she confirmed, and the catch: her wording did not match her records. That was settled with Mara, not with the advisor. |
| Click **Message client**. Type: **"Tell her she should take it from the rollover IRA and that it will be tax-free."** Click **Draft reply**. | Now the advisor writes back, and is a little careless. |
| Point at the **Agent trace**, top to bottom. | A drafter writes it. A compliance reviewer quotes the exact words that read as advice. The drafter revises, and it passes. The advisor still edits and sends. |
| Click **Send as clarification**. Switch to the client window, open **My requests**. | Mara sees the question in her own workspace and can answer it there. When she does, the case goes straight back to the top of the advisor's queue. |

## 3:55 Why LPL buys it (25 seconds, slide)

> LPL connects investors with about thirty-two thousand advisors. Coherent is the layer between them.
>
> Every confirmed case pairs a client's own words with what they meant. That vocabulary grows with use, and it sits behind a guard layer that keeps the model away from account facts. LPL could build this. Buying it is faster. That is our proposal, not a claim about LPL's roadmap.

## 4:20 AWS (20 seconds, slide)

> Amazon Bedrock in us-east-1, with Claude Haiku 4.5 from the approved list. Each agent is one schema-forced Bedrock call with a deterministic fallback. Cognito signs clients in, and DynamoDB holds their records. Our code, not the model, holds the account facts and computes the compliance verdict. No hard-coded keys. Synthetic data only.

Voice input uses the browser's speech service. Say so if asked; do not describe it as Amazon Transcribe.

## 4:40 Impact and close (20 seconds, advisor window, **Impact** in the sidebar)

| Do | Say |
| --- | --- |
| Point at **Measured in this workspace**, then at the **Advisor capacity model**. Change one input. | What we measured today is small and real: turns and seconds to a confirmed request. What we did not measure is here as a formula. Five unclear requests a week at ten minutes each is about one point three million advisor hours a year, and both inputs are assumptions. Change them. A pilot would measure them. |

> Coherent lets clients speak in their own words and gives advisors a request they can trust.

## If you are running long

Cut in this order. Each saves about ten seconds.

1. Switching back to the client window after sending. Say "Mara sees it in her workspace" instead.
2. Pointing at the request document. Go straight to **Confirm and send request**.
3. The second sentence of the AWS section.
4. Changing an input in the capacity model. Point at it instead.

Never cut the client confirming, the mismatch notice, or the compliance reviewer quoting the draft. Those three are the product.

## The reply beat on live Bedrock

In mock mode this beat is deterministic: the instruction above produces a first draft containing "you should" and "tax-free", the reviewer flags two issues, the drafter revises, and the review passes. That was run end to end through the API.

On live Bedrock it has **not** been run. The drafter is instructed never to give advice, so it may write a clean first draft, and then the trace shows only "Wrote the first draft" and "Passed". That is still a correct result, but it hides the loop. If that happens in rehearsal, use this path instead:

1. Click **Draft reply** with no instruction.
2. In the draft box, add: **"You should take it from the rollover IRA. It will be tax-free."**
3. Click **Re-check**. The reviewer flags the edit and quotes the words.
4. Say: "The advisor edited the draft, and the reviewer caught it before it reached the client. Sending anyway is possible, and the override is recorded on the case."

Pick whichever path worked in rehearsal and use only that one on the day.

A shorter alternative to the whole beat is **Send to client** on the prepared reply card: tick the items to confirm, edit the message if needed, and send. It is faster but does not show the reviewer catching anything.

## What is live and what is simulated

Keep this on a slide and say it if asked.

- **Live AWS:** Cognito sign-in, DynamoDB client records and archived request documents, and Bedrock for interpretation, triage, the prepared action packet, the prep brief, the reply drafter, the compliance reviewer, the next-steps planner, and the security investigator.
- **Deterministic code, never the model:** account facts and their sources, authorization, security routing, advisor ranking, queue priority, and the compliance verdict.
- **Synthetic:** every client, account, balance, event, and advisor. Messages between advisor and client stay inside the app; no email or SMS is sent, and no transaction or appointment is executed.
- **Measured:** client turns and seconds from first message to confirmation, for requests submitted in this workspace.
- **Not measured:** advisor time saved, or retention. The capacity model is a formula with assumed inputs.

## Reset between runs

1. Run `python -m backend.reset_demo`. New cases and assignments are cleared; no restart is needed.
2. Reload both windows. The queue should show only the four seed cases, with `CASE-1042` unassigned.

## If something fails

- **Microphone fails:** type the same sentence. The typed path is the same flow.
- **Signed out mid-demo:** the Cognito session expired. Sign in again; a request draft is restored and is not submitted automatically.
- **Bedrock is slow or throttled:** wait a second and resend once. If it still fails, say the live call did not return and narrate the advisor side with seed case `CASE-1042`, which holds the same scenario.
- **A dashboard agent card fails:** click its refresh button once. If it still fails, move on; the case, the queue, and assignment do not depend on it.
- **App will not start:** play the backup recording and say so.

## Likely questions

- **Why not build it yourselves?** You could. What you would be buying is time: a vocabulary that pairs clients' raw words with what they confirmed they meant, the guard layer that keeps the model away from account facts, and the tests around both.
- **AWS told us not to build multi-agent systems on day one. Why did you?** There is no orchestration framework. Each agent is a single Bedrock call that must answer through one tool with a fixed schema, and each has a deterministic fallback. The only loop is draft, review, one revision, review, and plain code runs it.
- **Where do your impact numbers come from?** Two are measured in the demo: turns and seconds to a confirmed request. The annual hours figure is a formula on screen with editable inputs. In a pilot we would measure time to the right destination, contacts needed to clarify, and how often staff override the suggestion.
- **Why an agent and not a form?** A form needs the client to already know the term. The agent starts from their words and checks them against their accounts.
- **What stops the model inventing an account?** It can only suggest accounts returned by the backend's lookup, the client must confirm, and staff see the source of every account fact.
- **Can the compliance reviewer be wrong?** Yes. That is why the verdict is computed in code from what the reviewer quoted, the advisor sees the quote, and an override is recorded on the case. It is a first check, not a replacement for supervision.
- **Is this advice?** No. It creates and routes a service request. It does not recommend or execute anything.
- **What would production need?** MFA and password reset, HTTPS with secure cookies, the firm's advisor directory with verified licence and state eligibility, audit logging, moving cases from local SQLite to managed storage, and compliance review of the glossary and the reviewer's rules.
