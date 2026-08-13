# Open Lakehouse Contract (OLC)

This project uses **Open Lakehouse Contracts** (`*.olc.yaml`): one YAML file per data
product declaring schema, quality (SQL rules), PII/masking, lineage, materialization, and
SLOs, executed by a conforming runtime. **Intent lives in the contract; the engine is a
flag chosen at apply time.**

## Rules
- **Validate** every contract against `schema/open-lakehouse-contract.schema.json` — run
  `olc validate <path>` (or `python scripts/validate.py <path>`); fix each
  `location: message` error until it passes.
- **Stay SQL-native**: quality rules and transforms are SQL (`sql: "amount > 0"`).
- **Never hard-code the engine**: `materialization` sets `strategy` + `format`; the
  provider is chosen at apply time.
- **Preserve intent on changes**: keep `primary_key`, `quality`, `materialization`, `pii`,
  and `service_levels` satisfied, or change the contract deliberately and flag the
  breaking diff.

## Verbs (also available as `/olc:*` commands)
`discover` → `contract` → `review` → `validate` → `impact`.
