---
name: open-lakehouse-contract
description: Author, validate, review, and reason about Open Lakehouse Contracts (*.olc.yaml) — portable, SQL-native data-product contracts covering schema, quality, PII, lineage, materialization, and SLOs. Use when creating or changing a data product, reviewing a PR that touches data, or answering what must be true about a dataset.
---

# Open Lakehouse Contract

An **Open Lakehouse Contract (OLC)** is one YAML file that defines a data product —
schema, quality (SQL rules), PII/masking, lineage, materialization, and SLOs — and is
executed by a conforming runtime. **Intent lives in the contract; the engine is a flag
chosen at apply time.** The same contract runs on Spark / DuckDB / Polars → Delta /
Iceberg / DuckLake.

## When to use this skill
- **Creating or updating a data product** → author or update an `*.olc.yaml`.
- **Reviewing a change that touches data** → compare the change to the applicable
  contract and flag breaking changes (schema/quality/PII/materialization/SLO).
- **Answering "what must be true about this data product?"** → read its contract.

## Working rules
1. **The schema is the source of truth.** Validate every contract against
   `schema/open-lakehouse-contract.schema.json` — run `olc validate <path>` (or
   `python scripts/validate.py <path>`), read `location: message` errors, and fix until
   it passes.
2. **Stay SQL-native.** Express quality rules and transforms as SQL
   (`sql: "amount > 0"`), not bespoke check objects. SQL is the portability invariant.
3. **Never hard-code the engine.** `materialization` sets `strategy` + `format`; the
   runtime/provider is chosen later (`--provider`), never inside the contract.
4. **Preserve intent on changes.** When editing an implementation, keep the contract's
   `primary_key`, `quality`, `materialization`, `pii`, and `service_levels` satisfied —
   or change the contract deliberately and call out the breaking diff.
5. **Persist intent.** Put durable requirements ("`customer_id` must never be null;
   refresh every 2h") into the contract, not a chat message — the contract outlives the
   conversation, the tool, and the platform.

## Verbs (slash commands, if installed)
`/olc:discover` · `/olc:contract <product>` · `/olc:impact "<change>"` ·
`/olc:review` · `/olc:validate`

## A minimal contract
```yaml
version: 1.0.0
info: { title: Orders, table_name: orders, target_layer: silver }
model:
  fields:
    - { name: order_id, type: integer, required: true }
    - { name: customer_email, type: string, pii: true, masking: partial }
    - { name: amount, type: float, required: true }
primary_key: [order_id]
quality:
  row_rules:
    - { name: positive_amount, sql: "amount > 0" }
materialization: { strategy: merge, format: iceberg }
```

The full field reference lives under `docs/reference/` in this repository.
