---
trigger: glob
globs: **/*.olc.yaml
description: Open Lakehouse Contract (OLC) — author, validate, and review data-product contracts
---
# Open Lakehouse Contract (OLC)

An OLC is one YAML file (`*.olc.yaml`) that defines a data product — schema, quality (SQL
rules), PII/masking, lineage, materialization, and SLOs — executed by a conforming
runtime. **Intent lives in the contract; the engine is a flag chosen at apply time.**

## Rules
- **Validate** against `schema/open-lakehouse-contract.schema.json` — run
  `olc validate <path>` (or `python scripts/validate.py <path>`); fix `location: message`
  errors until it passes.
- **Stay SQL-native**: rules and transforms are SQL (`sql: "amount > 0"`).
- **Never hard-code the engine**: `materialization` sets `strategy` + `format`; the
  provider is chosen at apply time.
- **Preserve intent on changes**: keep `primary_key`, `quality`, `materialization`, `pii`,
  and `service_levels` satisfied, or change the contract deliberately and flag the
  breaking diff.

## Verbs
`discover` → `contract` → `review` → `validate` → `impact`. On a change that touches data,
run **review**: compare it to the contract and give a PASS/FAIL on breaking schema /
quality / PII / SLO / materialization changes.
