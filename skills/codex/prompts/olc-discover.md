Discover the data products in this repository and propose Open Lakehouse Contracts.

1. Scan for data assets: SQL/dbt models, pipeline definitions, table DDL, existing
   schemas, and any `*.olc.yaml`.
2. Identify distinct data products — name, target layer, grain, sources, likely consumers.
3. Propose an OLC contract for each (valid against
   `schema/open-lakehouse-contract.schema.json`) covering schema, quality (SQL rules),
   PII, materialization, and SLOs. Prefer updating an existing contract over duplicating.
4. Validate all drafts: `olc validate` (or `python scripts/validate.py`).
5. Summarise findings as a short table: data product -> layer -> key rules -> SLO.

Keep it SQL-native and engine-agnostic.
