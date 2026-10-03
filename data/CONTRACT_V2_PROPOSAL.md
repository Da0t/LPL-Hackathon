# Proposed optional fields for a version-two contract

> **Status:** a proposal from the initial build, written against the legacy staff page in `frontend/staff/`. Kept for reference; it does not describe the current `web/` dashboard.

Version one is frozen and this branch does not change it. The product spec asks the staff view to show a few things that version one's responses do not carry. Every field below is **optional**: the staff page already reads each one when present and works without it. Adopting any of them is a team decision.

Preview them with `python3 frontend/staff/dev_server.py --v2`.

## GET /staff/cases/{case_id}

| Field | Type | Why | Without it the page shows |
| --- | --- | --- | --- |
| `preferred_contact_channel` | string | Spec page 1 lists the client's preferred contact channel. | Nothing |
| `client_confirmed_at` | ISO timestamp | Spec page 1 lists the client confirmation time. | "Confirmed by the client before sending" |
| `conflicts` | `[{statement, source_id}]` | Spec page 2: facts that conflict with the client's wording, each with a source. | The recorded account type only |
| `routing.reason` | string | Spec page 1: recommended destination "and why". | Destination only |
| `account_context.familiar_label` | string | The name the client knows the account by. | Nothing |
| `account_context.currency` | string | The balance's currency. The case-level `currency` describes the requested amount and is null when no amount was stated. | US dollars |
| `account_context.relevant_events[].summary` | string | Lets staff read what the event was, not just its type. | Event type only |

## GET /staff/cases/{case_id}/candidates

| Field | Type | Why | Without it the page shows |
| --- | --- | --- | --- |
| `existing_client_relationship` | boolean | The brief asks for the existing-client relationship on each candidate. | "Not reported" |
| `meeting_mode` | string array | Lets staff check the client's meeting preference. | Nothing |
| `capacity` | integer | Lets staff see how much room the advisor has. | Nothing |

## Not possible in version one

- **Choosing any advisor by name.** There is no directory endpoint, so overriding the suggestions means typing an advisor ID. A `GET /staff/advisors` list would fix this.
- **Changing the destination.** The spec lets staff change the destination or send a case back to the client, but the only write endpoint is `assign`. The page therefore shows the security destination and offers no action on it.
- **Assignment history.** `routing` keeps only the latest `assigned_advisor_id` and `staff_decision`.
