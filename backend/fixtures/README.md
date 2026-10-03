# Fallback fixtures (Agent 2)

These six files are a **verbatim copy of Agent 4's `data/*.json`** (branch
`codex/agent4-staff-data`), which extends the frozen `contracts/demo_fixture_v1.json`
with the same fixed IDs (`CLIENT-017`, `ACCT-201`, `ADV-03`, `CASE-1042`). Every record is
fictional.

The backend loads `data/` when it is present and complete; it falls back to this directory
otherwise, so the API behaves identically before and after Agent 4's branch is merged. The
backend never writes to either location. If Agent 4 changes `data/`, refresh this copy:

```bash
for f in clients accounts events advisors glossary cases; do cp data/$f.json backend/fixtures/$f.json; done
```

`cases.json` is optional seed data for the staff queue (the two fixture cases plus two more);
new live cases are numbered after the highest seeded case number, so the first live case is
`CASE-1043` as in the contract example.
