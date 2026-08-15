# Field Reference

The spec is a single JSON Schema (Draft 2020-12): [`schema/open-lakehouse-contract.schema.json`](https://github.com/LakeLogic/open-lakehouse-contract/blob/main/schema/open-lakehouse-contract.schema.json). It has **30 top-level fields** and **65 nested model definitions**. A contract requires `version`, `info`, and `model`; other capabilities are opt-in.

Typed OLC objects are strict: unknown keys fail validation instead of being silently ignored. Vendor-specific fields belong under the explicit `extensions` object and use a namespaced key such as `com.acme.retention`.

The schema is the source of truth — regenerate it any time with `python scripts/generate_schema.py` (see [Why Pydantic](../concepts/why-pydantic.md)). Below the fields are grouped by concern rather than listed flat — each links to the page that documents its options in full.

## Deep reference, by lifecycle stage

Each stage of a data product has a dedicated page enumerating every option, with examples:

<div class="grid cards" markdown>

- :material-sort-clock-ascending: **[Execution Order (pre & post)](execution-order.md)** — the full run sequence: where pre/post transforms and quality rules sit relative to the good/bad split and materialization.
- :material-database-import: **[Ingestion & Sources](ingestion.md)** — files, databases, APIs (dlt), streaming, CDC, micro-batch, load modes, partitioning.
- :material-broom: **[Post-Ingestion Lifecycle](lifecycle.md)** — delete / archive / retain consumed input, watermark, retry.
- :material-check-decagram: **[Validation & Quality](quality.md)** — row & dataset rules, severities, quarantine.
- :material-shield-lock: **[Security & PII](security.md)** — pii / phi / sensitive, masking, vault, security groups.
- :material-function-variant: **[Transformation](transformation.md)** — 20+ declarative ops + SQL escape hatch.
- :material-cog-transfer: **[External Logic](external-logic.md)** — plug in a Spark job / notebook / stored proc when it isn't one SQL statement; OLC still governs the output.
- :material-content-save: **[Materialization & Storage](materialization.md)** — strategy, format, SCD2, facts, soft-delete, schema evolution.
- :material-sitemap: **[Lineage](lineage.md)** — row provenance + the contract graph (`links` / `upstream` / `downstream`) + the Airflow-style pipeline DAG (`depends_on` / `external_sources`).
- :material-gauge: **[Service Levels (SLOs)](slo.md)** — freshness / availability / row-count objectives.
- :material-bell: **[Notifications](notifications.md)** — channels, events, templating.
- :material-file-document-outline: **[Unstructured / LLM Extraction](extraction.md)** — documents / audio / images → governed columns.

</div>

## Engines & libraries

The contract is portable because each concern is implemented by a well-known library, swapped per backend — the contract never mentions any of them:

| Concern | Library / engine |
|---|---|
| Contract models + validation | **Pydantic** (JSON Schema via `model_json_schema()`); **jsonschema** for language-neutral validation |
| Spark engine | **PySpark** (structured streaming for micro-batch) |
| DuckDB engine | **duckdb** (+ the `ducklake` extension) |
| Polars engine | **polars** / **pyarrow** |
| Delta format | **deltalake** (delta-rs) / **delta-spark** |
| Iceberg format | **pyiceberg** (+ Glue catalog) / Iceberg Spark framework |
| DuckLake format | DuckDB **`ducklake`** extension |
| Cloud object storage | DuckDB **httpfs** / **azure**; **s3fs** / **gcsfs** / **adlfs** (fsspec) |
| API ingestion | **dlt** (dlthub) |
| YAML parsing | **PyYAML** |
| LLM extraction | provider SDKs (**anthropic** / **openai**); **spaCy**, OCR (**tesseract**), **whisper** for preprocessing |
| Notifications | SMTP + webhook `POST` (**requests**), template rendering |

## Identity

| Field | Purpose | Reference |
|---|---|---|
| `version` **(required)** | Contract version, e.g. `1.0.0`. | [Getting Started](../getting-started.md#2-write-your-first-contract) |
| `info` **(required)** | Title, description, `table_name`, `target_layer`, owner. | [Getting Started](../getting-started.md#2-write-your-first-contract) |
| `extensions` | Namespaced vendor or organisation extensions, e.g. `com.acme.retention`. | — |
| `metadata` | Free-form metadata; also carries backend hints (e.g. DuckLake metadata/data paths). | [Providers → DuckDB/DuckLake](../providers/duckdb-ducklake.md) |
| `tier` | Data product tier / criticality. | [Service Levels (SLOs)](slo.md) |
| `contract_file_name` | Canonical file name for the contract. | — |

## Schema & keys

| Field | Purpose | Reference |
|---|---|---|
| `model` **(required)** | The declared shape — `model.fields[]` with `name`, `type`, `required`, `description`, and field-level `pii` / `masking`. | [Security & PII](security.md) · [Validation & Quality](quality.md#field-level-rules) |
| `primary_key` | Column(s) that uniquely identify a row; drives merge/SCD2 convergence. | [Materialization](materialization.md#write-strategies) |
| `natural_key` | Business key(s), distinct from a generated surrogate key. | [Materialization](materialization.md#scd2-history) |
| `schema_policy` | How to react to schema drift (evolve / warn / fail). | [Materialization → Schema evolution](materialization.md#schema-evolution) |

## Quality & quarantine

| Field | Purpose | Reference |
|---|---|---|
| `quality` | `row_rules[]` (per-row SQL predicates) and `dataset_rules[]` (uniqueness, referential, dataset-level checks). | [Validation & Quality](quality.md) |
| `quarantine` | Where and how failing rows are captured — **with the failed rule + reason** — instead of being dropped. | [Validation & Quality → Quarantine](quality.md#quarantine) |

## Transformation & lineage

| Field | Purpose | Reference |
|---|---|---|
| `source` | Where the input comes from (landing path, upstream table, etc.). | [Ingestion & Sources](ingestion.md) · [Post-Ingestion Lifecycle](lifecycle.md) |
| `transformations` | Declared, ordered steps between source and target (20+ ops + SQL). | [Transformation](transformation.md) |
| `logic` / `external_logic` | Inline code, or a referenced Spark job / notebook / stored proc. | [External Logic](external-logic.md) |
| `links` | Cross-dataset link registrations (a fact joining full upstream tables). | [Transformation → Joins](transformation.md#joins-lookups) · [Lineage → Graph](lineage.md#2-contract-level-lineage-graph) |
| `lineage` | `enabled: true` injects provenance columns on every row. | [Lineage → Row provenance](lineage.md#1-row-level-provenance) |
| `upstream` / `downstream` | Declared lineage edges to/from other data products. | [Lineage → Contract graph](lineage.md#2-contract-level-lineage-graph) |

## Materialization

| Field | Purpose | Reference |
|---|---|---|
| `materialization` | `strategy` (append / merge / scd2 / overwrite) + `format` (delta / iceberg / ducklake / native). The declarative-convergence target. | [Materialization & Storage](materialization.md) |
| `dataset` | Dataset-level materialization/registration attributes. | [Materialization & Storage](materialization.md) |
| `server` | Target server/warehouse connection context. | [Post-Ingestion Lifecycle](lifecycle.md#same-control-on-the-server-block) |
| `environments` | Per-environment overrides (dev / staging / prod). | [Materialization & Storage](materialization.md) |
| `schedule` | Intended run cadence. | [Ingestion & Sources → Load modes](ingestion.md#load-modes) |

## Governance & operations

| Field | Purpose | Reference |
|---|---|---|
| `compliance` | Compliance classification and controls. | [Security & PII](security.md#access-audit) |
| `service_levels` | SLOs — freshness, volume, availability targets. | [Service Levels (SLOs)](slo.md) |
| `observatory` | Observability/monitoring configuration. | [Notifications](notifications.md) |
| `extraction` | Unstructured / LLM extraction configuration (text → structured). | [Unstructured / LLM Extraction](extraction.md) |

## The minimal contract

```yaml
version: 1.0.0
info: { title: Orders, table_name: orders, target_layer: silver }
model:
  fields:
    - { name: order_id, type: string }
```

Everything else layers on top. See [`examples/orders.olc.yaml`](https://github.com/LakeLogic/open-lakehouse-contract/blob/main/examples/orders.olc.yaml) for a fuller annotated contract, and validate your own against the schema with the [Conformance Suite](conformance.md).

!!! note "Nested definitions"
    The 63 `$defs` are the nested models — `Materialization`, `Quarantine`, `Link`, `Field`, quality-rule variants, and so on. Because they're generated from Pydantic, each carries its own type constraints (enums, required sub-fields) that a JSON-Schema validator enforces for you.
