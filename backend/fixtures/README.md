# Fallback fixtures (Agent 2)

These files are **fallback synthetic data** used only when `data/` (owned by
Agent 4) is missing or incomplete. Every name, account, balance, event, and
advisor here is fictional. When Agent 4 publishes `data/clients.json`,
`data/accounts.json`, `data/events.json`, `data/advisors.json`, and
`data/glossary.json`, the backend loads those instead; it never modifies them.

The loader accepts each file as a JSON list, or as an object containing the
list under the entity name (`"clients"`, `"accounts"`, ...), `"items"`, or
`"data"`. Field names below are the canonical ones; the loader also accepts
the common alternatives noted in `backend/store.py`.
