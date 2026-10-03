# Coherent five-minute demo script

Everything shown is fictional: Mara Ellis, her accounts, the balances, and every advisor. This is the speaking and clicking plan. The judged deck still has to be built in the LPL PowerPoint template.

The spoken lines below total about 450 words. At a calm 150 words a minute that is three minutes of talking, which leaves two minutes for the app to respond, typing, and clicks. Rehearse with a timer; the cut list at the end says what to drop if you run long.

## Before you present

1. Start the backend from the repo root with live Bedrock (`SAMEPAGE_AI_MODE=bedrock`, see `README.md`). Open `http://127.0.0.1:8000/health` and check it says `"ai_mode":"bedrock"`. If it says `mock`, you are not showing the judged path.
2. Run `python -m backend.reset_demo`. The server does not need a restart.
3. Start the frontend: `cd web && PORT=3200 pnpm dev`.
4. Open two tabs side by side: `http://localhost:3200/intake` and `http://localhost:3200/dashboard`. Zoom both to about 125%.
5. On the dashboard tab, confirm the queue shows `CASE-1042` and `CASE-SEC-1`, and that the security case is at the top with a red dot.
6. Test the microphone once. If it is unreliable, type the request.
7. **Rehearse the reply beat on live Bedrock at least twice.** It is the one part of this script that has only been run in mock mode. See "The reply beat on live Bedrock" below.
8. Keep the backup recording open in a third tab.

Roles: one person speaks, one clicks, one watches the clock and calls the cuts.

## 0:00 Problem (35 seconds, slide)

> Clients know their life problem. They don't know the financial term for it.
>
> Meet Mara. Her husband needs care, and she needs six thousand dollars. She calls her account "the Roth thing from my old job." She doesn't have a Roth.
>
> If someone writes down what she said, an advisor gets a request about an account that doesn't exist, and Mara explains herself again to someone new.

## 0:35 Product (10 seconds, slide, then switch to the intake tab)

> Coherent turns everyday words into a confirmed request, checked against the client's own accounts, and hands the advisor a case they can act on.

## 0:45 Client demo (1 minute 30, live, intake tab)

| Do | Say |
| --- | --- |
| Demo client **Mara Ellis**, click **Start a request**. Speak or type: **"I need six thousand dollars from the Roth thing from my old job."** Click **Find the right next step**. | Mara just says what she needs. |
| Wait for the question and suggestions. Point at the routing graph. | Bedrock looked up her accounts. It did not guess. It says: I don't see a Roth IRA here. Could you mean your rollover IRA from your former employer? |
| Pick **Yes, my retirement account from former employer**. Then pick **Discuss taking $6,000 out**. | One question at a time, and every option comes from her real records. |
| Click **Review my request**. Check **What we understood**, the account, and the amount **6000**. | She reviews it in plain words. The amount is there only because she said it. |
| Click **Confirm and send**. Read the case number aloud. | She confirms. Nothing is sent without that. |

## 2:15 Advisor demo (1 minute 40, live, dashboard tab)

| Do | Say |
| --- | --- |
| Reload. Point at the red row at the top, then open Mara's new case. | The queue ranks itself and says why. A possible security issue goes to specialists first, never to a planning advisor. Here is Mara. |
| Point at the header line **Intake took 3 turns** and the **Prep brief**. | Three turns, under a minute, and the advisor opens a brief instead of a transcript. |
| Point at the quote and the amber notice. | Her exact words, what she confirmed, and the catch: her wording did not match her records. That was settled with Mara, not with the advisor. |
| Click **Message client**. Type: **"Tell her she should take it from the rollover IRA and that it will be tax-free."** Click **Draft reply**. | Now the advisor replies, and is a little careless. |
| Point at the **Agent trace**, top to bottom. | A drafter writes it. A compliance reviewer quotes the exact words that read as advice. The drafter revises, and it passes. The advisor still edits and sends. |
| Open the **Assign** tab. Click **Assign** on the first advisor. | The system suggests advisors and says why. A person decides. |

## 3:55 Why LPL buys it (25 seconds, slide)

> LPL connects investors with about thirty-two thousand advisors. Coherent is the layer between them.
>
> Every confirmed case pairs a client's own words with what they meant. That vocabulary grows with use, and it sits behind a guard layer that keeps the model away from account facts. LPL could build this. Buying it is faster. That is our proposal, not a claim about LPL's roadmap.

## 4:20 AWS (20 seconds, slide)

> Amazon Bedrock in us-east-1, with Claude Haiku 4.5 from the approved list. Each agent is one schema-forced Bedrock call with a deterministic fallback. Our code, not the model, holds the account facts and computes the compliance verdict. No hard-coded keys. Synthetic data only.

State accurately how voice input works in the build you are showing (Amazon Transcribe, browser speech recognition, or typed only).

## 4:40 Impact and close (20 seconds, dashboard tab, **Impact** in the sidebar)

| Do | Say |
| --- | --- |
| Point at **Measured in this workspace**, then at the **Advisor capacity model**. Change one input. | What we measured today is small and real: turns and seconds to a confirmed request. What we did not measure is here as a formula. Five unclear requests a week at ten minutes each is about one point three million advisor hours a year, and both inputs are assumptions. Change them. A pilot would measure them. |

> Coherent lets clients speak in their own words and gives advisors a request they can trust.

## If you are running long

Cut in this order. Each saves about ten seconds.

1. The **Assign** step. Say "a person assigns it" over the case header.
2. The routing graph mention in the client demo.
3. The second sentence of the AWS section.
4. Changing an input in the capacity model. Point at it instead.

Never cut the client confirming, the mismatch notice, or the compliance reviewer quoting the draft. Those three are the product.

## The reply beat on live Bedrock

In mock mode this beat is deterministic: the instruction above produces a first draft containing "you should" and "tax-free", the reviewer flags two issues, the drafter revises, and the review passes. That was run end to end.

On live Bedrock it has **not** been run. The drafter is instructed never to give advice, so it may write a clean first draft, and then the trace shows only "Wrote the first draft" and "Passed". That is still a correct result, but it hides the loop. If that happens in rehearsal, use this path instead:

1. Click **Draft reply** with no instruction.
2. In the draft box, add: **"You should take it from the rollover IRA. It will be tax-free."**
3. Click **Re-check**. The reviewer flags the edit and quotes the words.
4. Say: "The advisor edited the draft, and the reviewer caught it before it reached the client. Sending anyway is possible, and the override is recorded on the case."

Pick whichever path worked in rehearsal and use only that one on the day.

## What is live and what is simulated

Keep this on a slide and say it if asked.

- **Live:** Bedrock interpretation, triage, the prep brief, the reply drafter, the compliance reviewer, the next-steps planner, and the security investigator. Case creation, the queue, and assignment.
- **Deterministic code, never the model:** account facts and their sources, authorization, security routing, advisor ranking, queue priority, and the compliance verdict.
- **Simulated:** sign-in (a demo role switcher), every client, account, balance, event, and advisor. No message is really sent to a client.
- **Measured:** client turns and seconds from first message to confirmation, for intakes run in this workspace.
- **Not measured:** advisor time saved, or retention. The capacity model is a formula with assumed inputs.

## Reset between runs

1. Run `python -m backend.reset_demo`. New cases and assignments are cleared; no restart is needed.
2. Reload both tabs. The queue should show only the four seed cases, with `CASE-1042` unassigned.

## If something fails

- **Microphone fails:** type the same sentence. The typed path is the same flow.
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
- **What would production need?** Real authentication, the firm's advisor directory with verified licence and state eligibility, audit logging, and compliance review of the glossary and the reviewer's rules.
