# Open Lakehouse Contract (OLC)

An OLC is one YAML file (`*.olc.yaml`) that defines a data product — schema, quality (SQL
rules), PII/masking, lineage, materialization, and SLOs — executed by a conforming
runtime. **Intent lives in the contract; the engine is a flag chosen at apply time.**

## Rules
- **Validate** every contract against `schema/open-lakehouse-contract.schema.json` — run
  `olc validate <path>` (or `python scripts/validate.py <path>`) and fix each
  `location: message` error until it passes.
- **Stay SQL-native**: express quality rules and transforms as SQL (`sql: "amount > 0"`),
  not bespoke check objects.
- **Never hard-code the engine**: `materialization` sets `strategy` + `format`; the
  provider is chosen at apply time.
- **Preserve intent on changes**: keep `primary_key`, `quality`, `materialization`, `pii`,
  and `service_levels` satisfied — or change the contract deliberately and flag the
  breaking diff.
- **Persist requirements** in the contract, not in chat.

## Verbs (data-native workflow)
`discover` → `contract` → `review` → `validate` → `impact`. On a change that touches data,
run **review** (the merge gate): compare the change to the contract and answer PASS/FAIL
on breaking schema / quality / PII / SLO / materialization changes.
