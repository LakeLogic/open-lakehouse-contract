---
description: Generate or update an Open Lakehouse Contract for a data product
argument-hint: "\"<data product name or intent>\""
allowed-tools: Bash(olc:*), Bash(python:*), Read, Write, Edit, Glob, Grep
---
Create or update an Open Lakehouse Contract for: **$ARGUMENTS**

1. **Understand the data product.** Inspect the repo for the relevant source(s), grain,
   and consumers — existing `*.olc.yaml`, SQL / dbt models, pipeline definitions, table
   DDL. Read the schema at `schema/open-lakehouse-contract.schema.json` for the exact
   field vocabulary.
2. **Draft `contract.olc.yaml`** that is **valid against that schema**. Cover:
   - `info` (title, table_name, target_layer)
   - `model.fields` with types, `required`, and `pii` / `masking` on sensitive fields
   - `primary_key`
   - `quality.row_rules` as **SQL predicates** (e.g. `sql: "amount > 0"`) — stay SQL-native
   - `materialization` (`strategy` + `format`) — **never hard-code an engine**
   - `service_levels` if freshness / volume matter
3. **Validate and fix.** Run `!olc validate <path>` and correct any errors until it passes.
4. **Show** the contract and a one-paragraph rationale (sources, grain, key decisions).

Prefer updating an existing contract over duplicating one. Intent lives in the contract;
the engine/provider is chosen later at apply time, not here.
