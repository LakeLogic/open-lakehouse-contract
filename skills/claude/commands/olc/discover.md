---
description: Analyse the repo and propose Open Lakehouse Contracts for its data products
allowed-tools: Bash(olc:*), Bash(python:*), Read, Write, Glob, Grep
---
Discover the data products in this repository and propose Open Lakehouse Contracts.

1. **Scan** for data assets: SQL / dbt models, pipeline definitions, table DDL, existing
   schemas, and any `*.olc.yaml` already present.
2. **Identify** distinct data products — for each: name, target layer, grain, source(s),
   and likely consumers.
3. **Propose** an OLC contract for each (valid against
   `schema/open-lakehouse-contract.schema.json`), covering schema, quality (SQL rules),
   PII, materialization, and SLOs. Prefer updating an existing contract over duplicating.
4. **Validate** all drafts: !`olc validate`
5. **Summarise** what you found and what you propose — a short table of
   (data product → layer → key rules → SLO).

Keep it SQL-native and engine-agnostic: the contract states intent; the runtime executes it.
