Create or update an Open Lakehouse Contract for the data product described by: $ARGUMENTS

1. Understand the data product from the repo — sources, grain, consumers (existing
   `*.olc.yaml`, SQL/dbt models, pipeline definitions, DDL). Read the field vocabulary in
   `schema/open-lakehouse-contract.schema.json`.
2. Draft `contract.olc.yaml`, valid against that schema, covering: `info`, `model.fields`
   (with `pii`/`masking` on sensitive fields), `primary_key`, `quality.row_rules` as SQL
   predicates (stay SQL-native), `materialization` (strategy + format, never an engine),
   and `service_levels` if freshness/volume matter.
3. Validate and fix: run `olc validate <path>` (or `python scripts/validate.py <path>`)
   until it passes.
4. Show the contract and a one-paragraph rationale.

Intent lives in the contract; the engine/provider is chosen later at apply time.
