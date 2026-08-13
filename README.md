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

## SQL-native

**If you know SQL, you already know how to transform data in OLC.** Logic is expressed as SQL — the universal data language — not Python, not Spark code, not notebooks. The contract carries the SQL; a conforming runtime runs it, unchanged, on whichever engine you point it at.

```yaml
transformations:
  - sql: |
      SELECT o.*,
             ROUND(o.quantity * o.unit_price * (1 - COALESCE(o.discount_pct, 0)), 2) AS line_total,
             c.name AS customer_name
      FROM source o
      LEFT JOIN customers c ON o.customer_id = c.customer_id
    phase: post
```

The shorthand ops (`rename`, `filter`, `cast`, `join`, `rollup`, …) are just convenience wrappers that **compile to SQL** — every one shows its SQL variant in the [Transformation reference](docs/reference/transformation.md). Start with shorthand for the routine cases, drop to `sql:` the moment it gets bespoke — no rewrite, same contract. That's what makes OLC **portable**: SQL is the invariant, and the runtime rewrites dialect differences per engine (**PySpark** / **duckdb** / **polars**).

## Why OLC

- **SQL-native.** Transformation logic is SQL, so it's readable by analysts and engineers alike and runs on any SQL engine. No translation layer between what you write and what runs.
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

## Complements ODCS

OLC **complements the [Open Data Contract Standard (ODCS)](https://github.com/bitol-io/open-data-contract-standard)** — it doesn't compete with it. ODCS is the excellent, widely-adopted standard for *describing* a data contract; OLC adds the *executable, lakehouse-scoped* layer that runs it. The reference runtime imports ODCS and can export back to it (ODCS field names are accepted as aliases), so you can **import ODCS → run as OLC → export ODCS** with nothing lost either direction. See [OLC & ODCS](docs/concepts/vs-odcs.md).

## Part of a spec-driven movement

OLC is spec-driven development for the **data plane**: humans and AI agree on a precise, machine-checkable contract, then agents generate, validate against, and execute it. It's the same conviction behind **[OpenSpec](https://github.com/Fission-AI/openspec)** (~65k★, spec-driven development for AI *coding* assistants) and **ODCS** (the descriptive data-contract standard) — a precise, executable spec is the best interface between humans and AI. See [Agent-Native](docs/concepts/agent-native.md).

## Status

Draft `v1`. The schema is generated from the reference implementation and covers 28 top-level fields (schema, quality, materialization, lineage, PII/masking, SLOs, sources/links, environments, and more). Governance, formal versioning, and a language-neutral test corpus are on the roadmap — contributions welcome.

---

*Reference implementation: [LakeLogic](https://lakelogic.org). This repo is the open specification; it is intentionally vendor-neutral.*
