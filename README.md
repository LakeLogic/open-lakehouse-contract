<div align="center">

<img src="assets/banner.svg" alt="Open Lakehouse Contract — a portable, executable, SQL-native contract for the lakehouse" width="860">

![Spec](https://img.shields.io/badge/spec-v1%20draft-2965b3?style=flat-square)
![License](https://img.shields.io/badge/license-Apache%202.0-2965b3?style=flat-square)
![JSON Schema](https://img.shields.io/badge/JSON%20Schema-2020--12-6a737d?style=flat-square)
![Engines](https://img.shields.io/badge/engines-Spark%20%7C%20DuckDB%20%7C%20Polars-2e7d32?style=flat-square)
![Formats](https://img.shields.io/badge/formats-Delta%20%7C%20Iceberg%20%7C%20DuckLake-6f42c1?style=flat-square)
![Reference runtime](https://img.shields.io/badge/reference%20runtime-LakeLogic-e36209?style=flat-square)

**Designed to complement, not replace, data-contract standards like [ODCS](https://github.com/bitol-io/open-data-contract-standard).** OLC adds portable execution and lakehouse engineering semantics; the [LakeLogic](https://lakelogic.org) reference runtime consumes both. → *ODCS standardises the agreement · OLC standardises the execution · LakeLogic runs both.*

</div>

> [!TIP]
> **One contract defines a data product** — schema, quality, PII, lineage, materialization, SLOs — and a *conforming runtime executes that intent*, unchanged, across compatible lakehouse engines: Spark / DuckDB / Polars → Delta / Iceberg / DuckLake, on Databricks / Snowflake / Fabric / BigQuery / AWS / MotherDuck. The contract is the invariant; the runtime and backend are pluggable. → **[Read the docs](docs/index.md)**

**Our philosophy:**

```
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

That's the whole thing: what the data *is*, the rules it must pass, how it's written. A conforming runtime validates, quarantines, masks, and materializes straight from this file — so the standard and the implementation can't drift.

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

**If you know SQL, you already know how to transform data in OLC.** Logic is SQL — the universal data language — not Python, not Spark code, not notebooks. The contract carries the SQL; the runtime runs it, unchanged, on whichever engine you point it at.

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

The [providers matrix](docs/providers/index.md) runs the **same** RideFlow contract set across seven backends — each page shows the identical contract, the runtime invocation, and what it materialized (honest ✅ Live / ◑ Static-validated labels). Think of it as the OLC equivalent of a Terraform provider registry: one universal contract, many backends.

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
- **Reference implementation** — [LakeLogic](https://lakelogic.org)'s **Pydantic** models + Core, which *execute* the intent. The JSON Schema is generated from these models, so it can't drift from a working runtime.

The Pydantic models are the **reference implementation, not the specification itself** — a second runtime, in any language, is free to implement the same spec. Regenerate the schema whenever the reference models change:

```bash
pip install lakelogic
python scripts/generate_schema.py     # schema/ ← the reference DataContract models
```

## Complements ODCS

OLC **complements the [Open Data Contract Standard (ODCS)](https://github.com/bitol-io/open-data-contract-standard)** — it doesn't compete with it. ODCS is the excellent, widely-adopted standard for the *business + semantic agreement* about a data product; OLC adds the *engineering + runtime* contract that executes it.

|  | ODCS | Open Lakehouse Contract |
|---|---|---|
| Ownership · stakeholders · business semantics | ✅ defines | reference / integrate |
| Schema · terms · SLA · quality expectations | ✅ defines | ✅ **enforces at runtime** |
| PII classification | ✅ classifies | ✅ **masks at runtime** |
| SQL rules | some representation | **core design principle** |
| Materialization (merge/append, Delta/Iceberg/DuckLake) | — | ✅ |
| Engine execution (Spark/DuckDB/Polars) · runtime portability | not its role | ✅ **core objective** |

**ODCS standardises the agreement · OLC standardises the execution · the [LakeLogic](https://lakelogic.org) reference runtime runs both.** It imports ODCS and exports back (field names accepted as aliases), so **import ODCS → run as OLC → export ODCS** loses nothing either direction — and (proposed) an OLC file can *reference* an ODCS document rather than duplicate it. See [OLC & ODCS](docs/concepts/vs-odcs.md).

## Part of a spec-driven movement

OLC is spec-driven development for the **data plane**: humans and AI agree on a precise, machine-checkable contract, then agents generate, validate against, and execute it. Same conviction behind **[OpenSpec](https://github.com/Fission-AI/openspec)** (spec-driven development for AI *coding* assistants) and **ODCS** (the descriptive data-contract standard) — *a precise, executable spec is the best interface between humans and AI.* See [Agent-Native](docs/concepts/agent-native.md) and the [Agent Workflow](docs/concepts/agent-workflow.md).

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

Draft `v1`. The schema is generated from the reference implementation and covers **28 top-level fields** across schema, quality, materialization, lineage, PII/masking, SLOs, sources/links, environments, and more. Governance, formal versioning, and a language-neutral test corpus are on the roadmap — contributions welcome.

## License

[Apache License 2.0](LICENSE). The Open Lakehouse Contract is an open specification — free to implement, extend, and build on.

---

<div align="center">

*Reference implementation: **[LakeLogic](https://lakelogic.org)**. This repo is the open specification — intentionally vendor-neutral.*

</div>
