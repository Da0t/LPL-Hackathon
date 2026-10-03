# SamePage synthetic data

Every record here is fictional. No real client, advisor, account, or market data is used.

Each file is `{ "meta": {...}, "<name>": [...] }`, where `<name>` matches the file name and the key used in `contracts/demo_fixture_v1.json`. Merging the arrays gives the fixture's shape with more rows.

| File | Rows | Notes |
| --- | --- | --- |
| `clients.json` | 3 | `CLIENT-017` Mara Ellis, `CLIENT-022` Evan Brooks, `CLIENT-031` Lena Marchetti |
| `accounts.json` | 8 | Owner, type, familiar label, masked ID, balance snapshot, `balance_as_of`, `source_id` |
| `events.json` | 10 | Account, type, date, `source_id` |
| `advisors.json` | 8 | Specialties, active, available, meeting mode, capacity. `meta.specialist_queues` describes the security queue |
| `glossary.json` | 10 | The ten approved terms from the product spec |
| `cases.json` | 4 | Optional queue seed: the two fixture cases plus a Roth IRA question and a beneficiary request |

Run `python3 data/validate_data.py` from the repository root. It checks references between files, row counts, masked identifiers, dates, the ten glossary terms, that each demo scenario is still supported, and that every fixture record is present with unchanged values.

## Scenarios the data supports

| Client says | What the records contain | Expected handling |
| --- | --- | --- |
| Mara Ellis: "I need six thousand dollars from the Roth thing from my old job." | `ACCT-201` is a **rollover IRA** from a former employer (`EVENT-09`). She has **no Roth IRA**. | Agent notices the mismatch and asks. Case carries `client_term_did_not_match_account_type`. |
| Evan Brooks: "Can I put more money into my Roth IRA this year?" | `ACCT-301` is a Roth IRA. | Clear match. His existing advisor `ADV-01` is shown first. |
| Lena Marchetti: "I want my daughter to be the one who gets my retirement account if something happens to me." | `ACCT-401` traditional IRA with a 2018 beneficiary designation (`EVENT-31`); she also has a joint account. | `beneficiary_or_estate`. Existing advisor `ADV-07` first. |
| Evan Brooks: "I don't recognize a sign-in alert on my account." | `EVENT-24` sign-in alert. | `fraud_or_security`: security specialist queue, no advisor candidates. |

The client and account files hold no interpretations of these requests. `cases.json` contains example triage outputs for seeding the staff queue only; the live model must interpret each new request.

## Additions beyond the fixture (all optional)

`clients`: `state`, `client_since`. `accounts`: `ownership`, `opened_date`. `events`: `client_id`. `advisors`: `region`, `note`. `glossary`: `source_id`, `also_heard_as`. New account types: `traditional_ira`, `joint_brokerage`, `cash_management`. New routing destinations in seed cases: `advisor_review`, `estate_and_beneficiary_review`. `ADV-05` is unavailable and `ADV-08` is inactive, to exercise routing rules.

## For Agent 2

- Import cases from one place. `cases.json` already contains the two fixture cases, so loading both it and the fixture's `cases` would duplicate them.
- `python3 data/validate_data.py --export` prints all six files merged into one document with the fixture's shape, if a single file is easier to load.
- `ADV-08` is inactive and must never be a candidate. `ADV-05` is active but at capacity.
- Optional fields the staff page would use if the API sent them are in `CONTRACT_V2_PROPOSAL.md`. Nothing depends on them.
