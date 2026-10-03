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
  SAMEPAGE_AI_MODE=bedrock \
  python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

(Use `SAMEPAGE_AI_MODE=mock` for offline UI work , the app still runs, with
deterministic responses.)

**2. Start this app:**

```bash
cd web
pnpm install
PORT=3200 pnpm dev          # NOT 3000 , a stale service worker from another
                            # project hijacks localhost:3000. Use 3200.
```

Open **http://localhost:3200**.

- `/` , landing
- `/intake` , client intake (live Bedrock describe -> review -> send + routing graph)
- `/dashboard` , advisor workspace (queue, case detail, **AI prep brief**, actions,
  My pipeline board, compliance panel, impact charts)

It calls the backend at `http://127.0.0.1:8000` (override with
`NEXT_PUBLIC_SAMEPAGE_API`). CORS allows any localhost port.

## Design system

- Light theme, brand blue `#1677ff`, navy text `#152033`, Geist font.
- Logo: `public/coherent-logo.png` (lockup) and `public/coherent-icon.png` (mark);
  brand tokens in `app/globals.css`.
- API client: `lib/api.ts`. Everything is synthetic data; the role switcher is
  simulated access control, not production auth.

## Notes

- `components/agenda.tsx`, `call-to-action.tsx`, `features-3.tsx` are leftover v0
  template files (unused) , safe to delete; they're the only `tsc --noEmit`
  warnings.
- The `/lanyard` route and the 3D card components are from the template and are not
  part of the product flow.
