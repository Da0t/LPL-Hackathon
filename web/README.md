# Coherent , web app

The Coherent frontend for the LPL Financial hackathon: clients describe a service
need in plain language, Amazon Bedrock interprets and confirms it, and advisors get
a ready-to-act brief and resolve the request. Next.js (App Router) + Geist +
Tailwind, talking to the FastAPI + Amazon Bedrock backend in the repo root.

## Run it

**1. Start the backend** (repo root) with live Bedrock , see `../AWS_SETUP.md`:

```bash
cd ..                      # repo root
pip install -r requirements.txt
AWS_PROFILE=lpl-hackathon AWS_REGION=us-east-1 \
  BEDROCK_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0 \
  COHERENT_PORTAL_CONFIG=var/portal-aws.json SAMEPAGE_AI_MODE=bedrock \
  python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Provision Cognito and DynamoDB first using the root README. `SAMEPAGE_AI_MODE=mock` makes AI responses deterministic; authenticated portal access still needs AWS credentials.

**2. Start this app:**

```bash
cd web
pnpm install
PORT=3200 pnpm dev          # NOT 3000 , a stale service worker from another
                            # project hijacks localhost:3000. Use 3200.
```

Open **http://127.0.0.1:3200/login**. Private demo sign-ins are in ignored `../var/demo-access.json`.

For the [hosted AWS demo](https://d2gkrph97rdk92.cloudfront.net/login),
`scripts/deploy_aws.py` runs this Next.js server beside FastAPI on one EC2 instance and places
CloudFront in front of it. The four fictional character cards work without a password; email/password
sign-in remains available through Cognito. The public session cookie is HttpOnly and Secure. Deployment
details and the [architecture picture](../docs/architecture.svg) are in the root README.

- `/` , animated Coherent logo and replayable request-confirmation demo
- `/login` , one-click fictional demo characters, Cognito email/password sign-in, and animated
  request routing board
- `/workspace` , client overview with recorded-value chart, range tabs, account sparklines, and
  `/profile`, `/finances`, and `/requests` subpages
- `/workspace/requests/new` , step-by-step request editor and printable A4 document
- `/intake` , redirect to the authenticated request editor
- `/dashboard` , advisor workspace (priority queue, prepared action packet, agent panels,
  client messaging with compliance review, Pipeline board, Impact view)

Browser API calls use the same-origin `/api` proxy to `http://127.0.0.1:8000` on the EC2 host.
HttpOnly cookies authorize either server-signed demo sessions or Cognito sessions. Client requests
include current status and advisor clarification/reply threads alongside archived submission documents.

## Design system

- Light theme, brand blue `#1677ff`, navy text `#152033`, Geist font.
- Logo: `public/coherent-logo.png` (lockup) and `public/coherent-icon.png` (mark);
  brand tokens in `app/globals.css`.
- API clients: `lib/api.ts` and `lib/portal.ts`. Everything is synthetic data. The legacy role
  switcher is accepted only by the unconfigured backend; configured portal access uses Cognito or
  the fixed, signed one-click demo identities.

## Notes

- `npx tsc --noEmit` and `npm run build` validate the frontend with type checking enabled.
- The `/lanyard` route and the 3D card components are from the template and are not
  part of the product flow.

## Accessible client flow and visible agent evidence

The client workspace includes persistent larger-text, stronger-contrast, and automatic read-aloud
controls. Audio comes from authenticated Amazon Polly; voice input uses the browser speech service.
“My requests” shows plain-language status, readable message threads, and answers to advisor questions.
The reassurance bar links to a contact-request flow; it does not place a call.

Staff calls now use authenticated SSE. Agent evidence displays actual model/tool/source events and
uncalibrated confidence, with no simulated progress. Forge packets require a passing independent
record audit before their fields, drafts, and send controls appear. The backend also rejects
missing or stale approval receipts. Sentinel displays verified SEC/IRS KB excerpts alongside its
checklist. See the root README for corpus scope, AWS provisioning, limits, and browser acceptance.
