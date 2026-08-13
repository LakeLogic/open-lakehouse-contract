# Open Lakehouse Contract (OLC)

**One human-readable contract that both *describes* and *executes* a data product — portable across engines, table formats, and platforms.**

An Open Lakehouse Contract is a single YAML file that declares a dataset's **schema, quality rules, PII handling, lineage, materialization, and SLOs**. Unlike a descriptive data-contract spec, an OLC is **executable**: a conforming runtime validates, quarantines, enforces, and materializes straight from the file — so the standard and the implementation can't drift.

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

## Why OLC

- **Executable, not just descriptive.** The same file that documents the contract *runs* it — validation, quarantine, quality gates, PII masking, lineage, materialization. No spec-vs-implementation gap.
- **Portable.** One contract, every lakehouse. The *same* definitions run on **Spark / DuckDB / Polars**, materialize to **Delta / Iceberg / DuckLake**, on **Databricks / Snowflake / Fabric / BigQuery / AWS / MotherDuck**. The contract is the invariant; the backend is swappable.
- **Broader than "data contract."** OLC covers the whole lakehouse surface — schema **+ quality + PII + lineage + materialization + SLOs** — not just schema.
- **Agent-native.** Because it's typed, self-validating, and executable, an OLC is the ideal substrate for AI data agents: they can *generate* it (schema-constrained), *self-correct* against validation errors, *act* and observe real outcomes, and reason about the same contract across every platform.

## What's in this repo

| Path | What |
|---|---|
| `schema/open-lakehouse-contract.schema.json` | The **spec**: JSON Schema (Draft 2020-12), the language-neutral source of truth. |
| `examples/` | Illustrative contracts. |
| `tests/` | A **conformance suite** — `valid/` must pass, `invalid/` must fail. |
| `scripts/generate_schema.py` | Regenerates the schema from the reference implementation. |
| `docs/` | Spec overview. |

## The schema is *derived*, never hand-maintained

The JSON Schema is generated from the **reference implementation**'s typed models (Pydantic), so the standard tracks a working runtime rather than a document that rots:

```bash
pip install lakelogic
python scripts/generate_schema.py     # schema/ ← the Pydantic DataContract model
```

That's what makes "open" honest: **the spec is the JSON Schema; [LakeLogic](https://lakelogic.org) is the canonical reference runtime that implements it.** Any tool in any language can validate OLC files against the schema.

## Documentation

A full documentation site lives in [`docs/`](docs/) (mkdocs-material):

```bash
pip install -r docs-requirements.txt
mkdocs serve            # http://127.0.0.1:8011
```

It includes a **[providers matrix](docs/providers/index.md)** — the same RideFlow contract set rendered across DuckDB/DuckLake, MotherDuck, Databricks, Snowflake, BigQuery, Fabric, and AWS, each with the identical contract, the runtime invocation, and what it materialized (with honest ✅ Live / ◑ Static-validated status labels). Think of it as the OLC equivalent of a Terraform provider registry: one universal contract, many backends.

## Validate a contract

```bash
pip install jsonschema pyyaml
python tests/conformance.py           # checks examples/ + tests/ against the schema
```

Or validate your own file against `schema/open-lakehouse-contract.schema.json` with any JSON-Schema validator.

## Relationship to ODCS

OLC is **interoperable with the [Open Data Contract Standard](https://github.com/bitol-io/open-data-contract-standard)**: the reference runtime imports ODCS and can export back to it. OLC's native vocabulary stays lean; ODCS field names are accepted as aliases. Think of OLC as the **executable, lakehouse-scoped** contract, with a round-trip to ODCS for the descriptive, schema-scoped world.

## Status

Draft `v1`. The schema is generated from the reference implementation and covers 28 top-level fields (schema, quality, materialization, lineage, PII/masking, SLOs, sources/links, environments, and more). Governance, formal versioning, and a language-neutral test corpus are on the roadmap — contributions welcome.

---

*Reference implementation: [LakeLogic](https://lakelogic.org). This repo is the open specification; it is intentionally vendor-neutral.*
