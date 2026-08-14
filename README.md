<div align="center">

<img src="assets/banner.svg" alt="Open Lakehouse Contract — one executable contract for a data product: ingest from any source, govern it, land it in an open lakehouse, publish it anywhere" width="100%">

<sub>**Engines** · [Spark](https://spark.apache.org) · [DuckDB](https://duckdb.org) · [Polars](https://pola.rs) &nbsp;&nbsp;|&nbsp;&nbsp; **Formats** · [Delta](https://delta.io) · [Iceberg](https://iceberg.apache.org) · [DuckLake](https://ducklake.select)</sub>

![License](https://img.shields.io/badge/license-Apache%202.0-2965b3?style=flat-square)
![Engines](https://img.shields.io/badge/engines-Spark%20%7C%20DuckDB%20%7C%20Polars-2e7d32?style=flat-square)
![Formats](https://img.shields.io/badge/formats-Delta%20%7C%20Iceberg%20%7C%20DuckLake-6f42c1?style=flat-square)
[![Reference runtime](https://img.shields.io/badge/reference%20runtime-LakeLogic-e36209?style=flat-square)](https://github.com/LakeLogic/LakeLogic)

**Designed to complement, not replace, data-contract standards like [ODCS](https://github.com/bitol-io/open-data-contract-standard).** OLC adds portable execution and lakehouse engineering semantics on top. → *ODCS standardises the agreement · OLC standardises the execution · the [LakeLogic](https://github.com/LakeLogic/LakeLogic) reference runtime runs both.*

</div>

**One executable contract for a data product — ingest from any source, govern it, land it in an open lakehouse, publish it anywhere. Portable · SQL-native · engine-agnostic.**

The *same* contract runs unchanged across:

| | |
|---|---|
| **Engines** | Spark · DuckDB · Polars |
| **Table formats** | Delta · Iceberg · DuckLake |
| **Platforms** | Databricks · Snowflake · Fabric · BigQuery · AWS · MotherDuck |

*One file governs the whole path — source, schema, quality, PII, lineage, transformation, materialization, SLOs. The contract is the invariant; the runtime and backend are pluggable.* **[Read the docs →](https://lakelogic.github.io/open-lakehouse-contract/)**

**Our philosophy:**

```
→ simple by design — plain YAML + SQL, nothing new to learn
→ executable, not just descriptive
→ SQL-native, not framework-specific
→ intent in the contract, engine as a flag
→ one artifact, readable by humans and agents
→ portable across every lakehouse — and every AI agent
→ the contract persists; the tool, model, and platform are replaceable
```

---

## The contract

```yaml
version: 1.0.0
info: { title: Orders, domain: sales, system: orders, table_name: silver_orders, target_layer: silver }

# where it comes from — read the sales-domain bronze table incrementally (by ordered_at)
source: { type: table, path: "table:lakehouse.sales.bronze_orders", load_mode: incremental, watermark_field: ordered_at }

model:
  fields:
    - { name: order_id,       type: integer,   required: true }
    - { name: customer_email, type: string,    pii: true, masking: partial }
    - { name: amount,         type: float,     required: true }
    - { name: order_total,    type: float }              # derived below
    - { name: ordered_at,     type: timestamp, required: true }
primary_key: [order_id]

# one declared step between source and target
transformations:
  - phase: pre
    derive: { field: order_total, sql: "amount + shipping_fee" }

quality:
  enforce_required: true                                     # completeness: required fields present
  row_rules:
    - { name: positive_amount, sql: "amount > 0" }           # correctness
  dataset_rules:
    - { name: order_id_unique, unique: order_id }            # completeness: no duplicate keys
    - null_ratio: { field: customer_email, max: 0.02, category: completeness }   # threshold: ≤2% nulls

# freshness + volume the runtime checks each run (delivery SLOs)
service_levels:
  freshness: { threshold: "1h", field: ordered_at }   # timeliness — measured against ordered_at
  row_count: { min_rows: 1 }                           # volume

# where it lands — converge the silver Iceberg table in the sales domain
materialization: { strategy: merge, format: iceberg, location: "s3://lakehouse/sales/orders/silver" }
```

**SQL-first, with business shorthands.** Any rule can be raw `sql: "…"` (like `positive_amount`); the shorthands — `unique`, `null_ratio`, `enforce_required` — are readable wrappers that **compile to the same SQL**. Reach for whichever reads clearer; the runtime runs SQL either way.

The whole path, one file — each block answers one question:

| Block | Answers |
|---|---|
| `source` | where the data comes from — the **primary** source (here, bronze); join more via `links` |
| `model` · `primary_key` | what it *is* — schema + keys |
| `transformations` | how it's shaped |
| `quality` | the rules it must pass — **correctness + completeness** (row rules, uniqueness, null-ratio thresholds) |
| `service_levels` | the delivery SLOs — **freshness + volume** (availability too) |
| `materialization` | where it lands (silver Iceberg) |

*Multi-source is first-class:* a contract reads one primary `source` and joins any number of additional sources via `links` — other tables, domains, or systems (e.g. enrich orders with a `customers` dim, or a `fx_rates` table for currency).

One runtime reads this file and does the rest — ingest → transform → validate → quarantine → mask → materialize → check SLOs. No spec-vs-code drift.

## See it in action

An AI agent proposes a contract; you review it; then data is materialized. Spec-driven development for the **data plane** — align before acting.

```text
You: /olc:contract "daily revenue by city from Stripe charges, drop test rows, freshness < 6h"

AI:  Created olc/changes/revenue-daily/
     ✓ proposal.md        — source: payments.silver_stripe_charges; grain: (date, city)
     ✓ contract.olc.yaml  — schema + quality + SLO + materialization: merge   [schema-valid]
     ✓ tasks.md           — wire source · add rules · set SLO · materialize

You: /olc:validate

AI:  Schema OK. Dry-run on 5,000 sample rows:
       4,812 kept · 188 quarantined (1.2% test rows, 2.5% negative fare) · freshness 3h ✓

You: /olc:apply --provider duckdb

AI:  Materialized silver.revenue_daily (merge, DuckLake) — 4,812 rows.
     Same contract runs unchanged on Spark/Delta, Snowflake, or BigQuery — just change --provider.
```

**That dry-run needs no real data.** `/olc:validate` generates **synthetic rows from the contract's own schema**, seeded with edge cases the gates should catch — so you prove the rules *before* wiring a live source:

| Injected edge case | Caught by |
|---|---|
| `test` / staging rows | the drop-test-rows rule |
| negative `fare` | `positive_amount` — **correctness** |
| nulls above 2% | `null_ratio` — **completeness** |
| duplicate keys | `order_id_unique` — **completeness** |
| stale timestamps | `freshness` SLO |

`lakelogic generate` synthesizes type-, range-, and rule-aware rows with a tunable invalid ratio; the agent reads the quarantine breakdown and self-corrects. Same dry-run, either way — **greenfield** (pure synthetic, zero data) or **brownfield** (a real sample from your source).

> [!NOTE]
> The contract never named an engine — `--provider` chose it at apply. The `/olc:*` verbs **ship today** for Claude Code and Codex (see below); the *execute-against-real-data* half comes from the reference runtime.

## Use it with your AI assistant

The workflow is **portable across AI agents** — same verbs, each assistant's native mechanism, no cloud required:

```bash
pip install -e .          # the `olc` CLI (validate + init)
olc init --tools all      # install integrations for every supported assistant
```

**Eleven assistants ship today** — Claude Code, Codex (ChatGPT), Gemini CLI, Cursor, GitHub Copilot, Windsurf, Cline, Amazon Q, Roo Code, Kilo Code, and the shared [`AGENTS.md`](https://agents.md) standard (OpenCode, Zed, Jules, …) — each in its native format:

- **Claude Code / Gemini CLI** — `/olc:validate` (schema check, works now) · `/olc:contract "<intent>"` · `/olc:review` (breaking-change merge gate) · `/olc:discover` · `/olc:impact`.
- **ChatGPT** — the same verbs as [Codex](https://github.com/openai/codex) prompts, or a Custom GPT with the schema as knowledge for the web.
- **Cursor / Copilot / Windsurf / Cline / Amazon Q / Roo / Kilo** — the OLC rules load automatically for `*.olc.yaml`.

Verbs are data-native — **discover → contract → review → validate → impact** — and the integration layer is open (no cloud). See [`skills/`](skills/) and the [Agent Workflow](docs/concepts/agent-workflow.md).

## SQL-native

**Know SQL? You already know OLC.** Logic is SQL — not Python, not Spark code, not notebooks. The contract carries the SQL; the runtime runs it unchanged on whichever engine you choose.

```yaml
transformations:
  - sql: |
      SELECT o.*,
             ROUND(o.quantity * o.unit_price * (1 - COALESCE(o.discount_pct, 0)), 2) AS line_total
      FROM source o
    phase: post
```

The shorthand ops (`rename`, `filter`, `cast`, `join`, `rollup`, …) are convenience wrappers that **compile to SQL** — each shows its SQL variant in the [Transformation reference](docs/reference/transformation.md). SQL is the portability invariant; the runtime rewrites dialect differences per engine (**PySpark** / **duckdb** / **polars**).

## Why OLC

- **SQL-native.** Logic is SQL — readable by analysts and engineers, runs on any SQL engine. No translation layer.
- **Executable, not just descriptive.** The same file that documents the contract *runs* it — validation, quarantine, quality gates, PII masking, lineage, materialization. No spec-vs-implementation gap.
- **Portable.** One contract, every lakehouse. Same definitions on **Spark / DuckDB / Polars** → **Delta / Iceberg / DuckLake**, on **Databricks / Snowflake / Fabric / BigQuery / AWS / MotherDuck**.
- **Broader than "data contract."** The whole lakehouse surface — schema **+ quality + PII + lineage + materialization + SLOs** — not just schema.
- **Agent-native.** Typed, self-validating, and executable — the ideal substrate for AI data agents to *generate*, *self-correct*, *act*, and reason across every platform.

## Providers — one contract, every lakehouse

The [providers matrix](docs/providers/index.md) runs the **same** contract set across seven backends — each page shows the identical contract, its invocation, and what it materialized (honest ✅ Live / ◑ Static-validated). Like a Terraform provider registry: one contract, many backends.

| DuckDB/DuckLake | MotherDuck | Databricks | Snowflake | BigQuery | Fabric | AWS/Glue |
|---|---|---|---|---|---|---|
| ✅ | ✅ | ✅ | ✅ | ✅ | ◑ | ✅ |

## Quickstart — validate a contract

The spec is a single JSON Schema; validate any OLC file against it in any language — **no runtime required**. Keep `*.olc.yaml` contracts beside your SQL / dbt / PySpark and gate every PR on them:

```bash
pip install jsonschema pyyaml
python scripts/validate.py                    # discovers + validates **/*.olc.yaml
python tests/conformance.py                   # (this repo) the spec's own conformance corpus
```

A ready-to-use GitHub Action lives in [`.github/workflows/validate-olc.yml`](.github/workflows/validate-olc.yml) — drop it into any repo (point `--schema` at the published schema URL) and contracts are checked on every push.

To *run* a contract, use the reference runtime:

```bash
pip install lakelogic
```
```python
from lakelogic import DataProcessor
proc = DataProcessor("orders.olc.yaml", engine="duckdb")   # or "spark" / "polars"
good, bad = proc.run(source_df)                            # validate + quarantine
proc.materialize(good, bad)                                # write per `materialization`
```

## Specification, schema, and reference implementation

OLC is deliberately **three separable layers**, so the standard never collapses into one vendor's code:

```
   Open Lakehouse Contract  ·  the specification — what the fields MEAN
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
   JSON Schema           Pydantic reference models
   structural            executable behaviour, in the
   validation,           reference runtime (LakeLogic)
   any language
```

- **Specification** — defines what `model`, `quality`, `primary_key`, `materialization`, `pii`, `service_levels`… *mean*. Language- and runtime-neutral; documented in the [field reference](docs/reference/schema.md).
- **JSON Schema** (`schema/open-lakehouse-contract.schema.json`) — the machine-readable *structural* form. Validate an OLC file in any language.
- **Reference implementation** — [LakeLogic](https://github.com/LakeLogic/LakeLogic)'s **Pydantic** models + Core, which *execute* the intent. The JSON Schema is generated from these models, so it can't drift from a working runtime.

The Pydantic models are the **reference implementation, not the spec** — any second runtime, in any language, may implement the same spec. Regenerate the schema when the models change:

```bash
pip install lakelogic
python scripts/generate_schema.py     # schema/ ← the reference DataContract models
```

## Complements ODCS

OLC **complements [ODCS](https://github.com/bitol-io/open-data-contract-standard)**, it doesn't compete. ODCS is the standard for the *business + semantic agreement*; OLC adds the *engineering + runtime* contract that executes it.

|  | ODCS | Open Lakehouse Contract |
|---|---|---|
| Ownership · stakeholders · business semantics | ✅ defines | reference / integrate |
| Schema · terms · SLA · quality expectations | ✅ defines | ✅ **enforces at runtime** |
| PII classification | ✅ classifies | ✅ **masks at runtime** |
| SQL rules | some representation | **core design principle** |
| Materialization (merge/append, Delta/Iceberg/DuckLake) | — | ✅ |
| Engine execution (Spark/DuckDB/Polars) · runtime portability | not its role | ✅ **core objective** |

**ODCS standardises the agreement · OLC standardises the execution · the [LakeLogic](https://github.com/LakeLogic/LakeLogic) reference runtime runs both.** It imports and exports ODCS losslessly — **import ODCS → run as OLC → export ODCS**. See [OLC & ODCS](docs/concepts/vs-odcs.md).

## Part of a spec-driven movement

Spec-driven development for the **data plane**: humans and AI agree on a precise, machine-checkable contract, then agents generate, validate, and execute it — the same conviction behind **[OpenSpec](https://github.com/Fission-AI/openspec)** (for AI coding) and **ODCS** (descriptive data contracts). See [Agent-Native](docs/concepts/agent-native.md) · [Agent Workflow](docs/concepts/agent-workflow.md).

## What's in this repo

| Path | What |
|---|---|
| `schema/open-lakehouse-contract.schema.json` | The **spec**: JSON Schema (Draft 2020-12), the language-neutral source of truth. |
| `olc/` | The `olc` **CLI** — `olc validate` (schema-only, no runtime) + `olc init` (install agent integrations). |
| `skills/` | **Agent integrations** — for Claude Code, Codex, Cursor, GitHub Copilot, Gemini, Windsurf, and Cline (installed by `olc init`). |
| `examples/` | Illustrative contracts. |
| `tests/` | A **conformance suite** — `valid/` must pass, `invalid/` must fail. |
| `scripts/` | `validate.py` (zero-install CI validator) + `generate_schema.py` (regenerate the schema). |
| `docs/` | The full documentation site (mkdocs-material) — concepts, providers, and a complete field reference. |

## Documentation

```bash
pip install -r docs-requirements.txt
mkdocs serve            # http://127.0.0.1:8011
```

Concepts (what/why/agent-native/agent-workflow/ODCS) · **[Providers matrix](docs/providers/index.md)** · a complete **[field reference](docs/reference/schema.md)** covering ingestion, lifecycle, quality, security, transformation, materialization, lineage, SLOs, notifications, and extraction.

## Status

Draft **v1**. Schema generated from the reference implementation — **28 top-level fields** (schema, quality, materialization, lineage, PII/masking, SLOs, sources/links, environments…). Governance, formal versioning, and a language-neutral corpus are on the roadmap — contributions welcome.

## License

[Apache License 2.0](LICENSE). The Open Lakehouse Contract is an open specification — free to implement, extend, and build on.

---

<div align="center">

*Reference implementation: **[LakeLogic](https://github.com/LakeLogic/LakeLogic)**. This repo is the open specification — intentionally vendor-neutral.*

</div>
