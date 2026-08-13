# Open Lakehouse Contract (OLC) — GitHub Copilot instructions

This repository uses **Open Lakehouse Contracts** (`*.olc.yaml`): one YAML file per data
product declaring schema, quality (SQL rules), PII/masking, lineage, materialization, and
SLOs, executed by a conforming runtime. **Intent lives in the contract; the engine is a
flag chosen at apply time.**

When creating or changing data products, or reviewing a change that touches data:

- **Validate** every contract against `schema/open-lakehouse-contract.schema.json` — run
  `olc validate <path>` (or `python scripts/validate.py <path>`) and fix each reported
  `location: message` error until it passes.
- **Stay SQL-native**: quality rules and transforms are SQL (`sql: "amount > 0"`), not
  bespoke check objects.
- **Never hard-code the engine**: `materialization` sets `strategy` + `format`; the
  provider is chosen at apply time, never inside the contract.
- **Preserve intent on changes**: keep `primary_key`, `quality`, `materialization`, `pii`,
  and `service_levels` satisfied — or change the contract deliberately and flag the
  breaking diff (a `merge` silently becoming `append`, a dropped rule, a widened PII field).
- **Persist requirements** in the contract, not in a chat message.

**Verbs (data-native workflow):** `discover` → `contract` → `review` → `validate` →
`impact`. When asked to review a PR that touches data, act as the merge gate: compare the
change to the applicable contract and answer PASS/FAIL — "does the data product still
satisfy its contract?", not just "did the code change?"
