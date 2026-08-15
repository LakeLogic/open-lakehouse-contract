---
title: Anatomy of a Contract
description: Every OLC block in one place — each section annotated with its options, then the full schema-valid contract assembled at the bottom.
---

# Anatomy of a Contract

Every OLC block, in one view — each section below is annotated with its common options, and the [**full contract**](#the-full-contract) is assembled at the bottom. For exhaustive field tables, see the [Field Reference](schema.md); each section links to its deep-dive page.

Everything here is one **schema-valid** contract — a silver `orders` data product in the `sales` domain. Download it: [`examples/full.olc.yaml`](https://github.com/LakeLogic/open-lakehouse-contract/blob/main/examples/full.olc.yaml).

!!! tip "SQL-first, business shorthands"
    Rules and transforms can be raw `sql: "…"` or business **shorthands** (`unique`, `null_ratio`, `not_null`, `filter`, `derive`) — the shorthands compile to the same SQL. Reach for whichever reads clearer.

---

## Identity — `info`

Names the product and places it in the mesh (`domain` · `system`), sets the target layer, and records ownership.

```yaml
version: 1.0.0
info:
  title: Orders                        # human-readable name
  domain: sales                        # mesh domain (namespace)
  system: orders                       # source system within the domain
  table_name: silver_orders            # physical table name
  target_layer: silver                 # bronze | silver | gold
  version: 1.0.0                       # contract version
  description: Cleaned, deduplicated orders — one row per order.
  owner: data-platform@acme.com        # accountable team
  contact: "#sales-data"               # where to reach them
  status: active                       # draft | active | deprecated
  classification: internal             # data classification
```

## Source — `source`

Where the data comes from — **one primary source**. `type` selects the reader (files, tables, databases, REST APIs, streams); `load_mode` + `watermark_field` drive incremental reads. → [Ingestion & Sources](ingestion.md)

```yaml
source:
  type: table                          # table | landing | database | api | stream
  path: "table:lakehouse.sales.bronze_orders"
  load_mode: incremental               # full | incremental
  watermark_field: ordered_at          # incremental cursor
  empty_behavior: skip                 # skip | fail
  # database:  type: database, query: "SELECT * FROM orders WHERE updated_at > :wm"
  # api:       type: api, dlt: { source: rest_api, base_url: "https://api.example.com/v2/" }
  # files:     type: landing, path: "s3://landing/sales/orders/", format: json
```

## Links — `links`

Additional sources to **join** — as many as you need (other tables, domains, or systems). → [Ingestion & Sources](ingestion.md)

```yaml
links:
  - { name: customers, type: table, path: "table:lakehouse.sales.silver_customers", columns: [customer_id, region] }
  - { name: fx_rates,  type: table, path: "table:lakehouse.reference.silver_fx_rates" }
```

## Model & keys — `model`, `primary_key`, `natural_key`

What the data **is**: typed fields, PII/masking, accepted values, ranges — plus the keys. → [Field Reference: Schema & keys](schema.md#schema-keys) · [Security & PII](security.md)

```yaml
model:
  grain: "one row per order"
  fields:
    - { name: order_id,       type: integer,   required: true, description: "Primary key." }
    - { name: customer_id,    type: integer,   required: true }
    - { name: customer_email, type: string,    pii: true, masking: partial }   # masked at runtime
    - { name: status,         type: string,    accepted_values: [placed, shipped, delivered, cancelled] }
    - { name: amount,         type: float,     required: true, min: 0 }
    - { name: order_total,    type: float }                    # derived below
    - { name: region,         type: string }                  # enriched from the customers link
    - { name: ordered_at,     type: timestamp, required: true }

primary_key:  [order_id]               # uniqueness / merge key
natural_key:  [order_id]               # business key (may differ from PK)
```

## Transformations — `transformations`

How the data is **shaped** — SQL-first, with shorthand ops (`derive`, `filter`, `rename`, `cast`, `join`, `rollup`, …) that compile to SQL. Each step runs in a `pre` or `post` phase. → [Transformation](transformation.md) · [Execution Order](execution-order.md)

```yaml
transformations:
  # SQL variant — full control, joins the linked sources
  - phase: pre
    sql: |
      SELECT o.*, c.region
      FROM source o
      LEFT JOIN customers c ON c.customer_id = o.customer_id
  # shorthand ops — readable wrappers
  - { phase: pre,  derive: { field: order_total, sql: "amount + shipping_fee" } }
  - { phase: pre,  filter: { sql: "status <> 'test'" } }
```

## Quality — `quality`

The rules the data must pass — **correctness** (`row_rules`, per-row → quarantine) and **completeness** (`enforce_required`, `dataset_rules` like `unique` and `null_ratio` thresholds). → [Validation & Quality](quality.md)

```yaml
quality:
  enforce_required: true               # completeness: required fields present
  fail_pipeline_on_dataset_error: false
  row_rules:
    - { name: positive_amount, sql: "amount > 0" }             # correctness (raw SQL)
    - { not_null: order_id }                                   # shorthand
    - { accepted_values: { field: status, values: [placed, shipped, delivered, cancelled] } }
    - { range: { field: amount, min: 0 } }
  dataset_rules:
    - { name: order_id_unique, unique: order_id }              # completeness: no dup keys
    - null_ratio: { field: customer_email, max: 0.02, category: completeness }   # threshold: <=2% nulls
```

## Service levels — `service_levels`

The **delivery SLOs** the framework checks each run: `freshness` (timeliness, measured against a timestamp `field`), `availability`, and `row_count` (volume bounds). → [Service Levels (SLOs)](slo.md)

```yaml
service_levels:
  freshness:    { threshold: "1h", field: ordered_at }         # timeliness vs a timestamp
  availability: { threshold: 0.99 }                            # uptime target
  row_count:    { min_rows: 1, max_rows: 10000000 }            # volume bounds
```

## Lineage — `lineage`

Provenance columns injected on every row (`_lakelogic_*`) — source path, run id, contract, domain/system, timestamps. Column names are configurable. → [Lineage](lineage.md)

```yaml
lineage:
  enabled: true                        # inject _lakelogic_* provenance columns
  capture_source_path: true
  capture_run_id: true
```

## Materialization — `materialization`

Where it **lands** and how it converges: write `strategy`, table `format`, `location`, partitioning — plus SCD2/fact semantics. → [Materialization & Storage](materialization.md)

```yaml
materialization:
  strategy: merge                      # append | overwrite | merge
  format: iceberg                      # delta | iceberg | ducklake | parquet
  location: "s3://lakehouse/sales/silver_orders"
  partition_by: [region]               # physical partitioning
  # scd2: { … }                        — slowly-changing dimension (type 2) history
  # fact: { type: transaction }        — fact-table semantics
```

## Server & output — `server`

The target/output connection context — the warehouse/store a run binds to, and whether it runs as a **Quality Gate** (`validate`) or **Raw-to-Bronze** movement (`ingest`). → [Server & Output](server.md)

```yaml
server:
  type: warehouse
  path: "s3://lakehouse/sales/silver_orders"
  mode: validate                       # validate — Quality Gate | ingest — Raw-to-Bronze
  format: parquet
  cast_to_string: false                # bronze: read every column as string
  schema_policy: { evolution: allow, unknown_fields: allow }
  post_ingestion: { action: retain }   # retain | delete | archive the consumed input
```

## Quarantine — `quarantine`

What happens to rows that fail `quality` — kept aside with the rule + reason, or made a hard failure. → [Validation & Quality](quality.md)

```yaml
quarantine:
  enabled: true
  include_error_reason: true           # keep rule + reason on each bad row
  fail_on_quarantine: false            # true = hard-fail the run on any bad row
  write_mode: append
```

## Schema policy — `schema_policy`

How schema drift is handled — evolution mode and what to do with unknown fields. → [Post-Ingestion Lifecycle](lifecycle.md)

```yaml
schema_policy:
  evolution: compatible                # strict | append | merge | overwrite | compatible | allow
  unknown_fields: quarantine           # quarantine | drop | allow
```

## Compliance — `compliance`

A **free-form** slot for classification & controls (regulations, residency, retention, approvals) — no fixed schema. It records the *why*; it's metadata, not a gate. → [Compliance](compliance.md)

```yaml
compliance:
  regulations: [GDPR, CCPA]
  data_residency: eu-west
  retention: { period: 400d, basis: legal }
  classification: confidential
```

## Edges — `upstream` / `downstream`

The data product's place in the mesh — declared dependencies and known consumers.

```yaml
upstream: ["sales.orders.bronze_orders"]
downstream:
  - { type: dashboard, name: "Sales Daily", platform: tableau, owner: analytics@acme.com }
```

## Operations — `tier`, `schedule`

Criticality tier and the run cadence.

```yaml
tier: gold                             # criticality tier
schedule: "0 * * * *"                  # cron — hourly
```

---

## The full contract

The whole thing assembled — copy-paste-able and schema-valid. Also on GitHub: [`examples/full.olc.yaml`](https://github.com/LakeLogic/open-lakehouse-contract/blob/main/examples/full.olc.yaml).

```yaml
version: 1.0.0

# ── IDENTITY ─────────────────────────────────────────────────────────────────
info:
  title: Orders
  domain: sales
  system: orders
  table_name: silver_orders
  target_layer: silver
  version: 1.0.0
  description: Cleaned, deduplicated orders — one row per order.
  owner: data-platform@acme.com
  contact: "#sales-data"
  status: active
  classification: internal

# ── SOURCE — where it comes from (one primary source) ────────────────────────
source:
  type: table
  path: "table:lakehouse.sales.bronze_orders"
  load_mode: incremental
  watermark_field: ordered_at
  empty_behavior: skip

# ── LINKS — additional sources to join ───────────────────────────────────────
links:
  - { name: customers, type: table, path: "table:lakehouse.sales.silver_customers", columns: [customer_id, region] }
  - { name: fx_rates,  type: table, path: "table:lakehouse.reference.silver_fx_rates" }

# ── MODEL — what it *is* (schema + keys) ─────────────────────────────────────
model:
  grain: "one row per order"
  fields:
    - { name: order_id,       type: integer,   required: true, description: "Primary key." }
    - { name: customer_id,    type: integer,   required: true }
    - { name: customer_email, type: string,    pii: true, masking: partial }
    - { name: status,         type: string,    accepted_values: [placed, shipped, delivered, cancelled] }
    - { name: amount,         type: float,     required: true, min: 0 }
    - { name: order_total,    type: float }
    - { name: region,         type: string }
    - { name: ordered_at,     type: timestamp, required: true }

primary_key:  [order_id]
natural_key:  [order_id]

# ── TRANSFORMATIONS — SQL-first; shorthands compile to SQL ───────────────────
transformations:
  - phase: pre
    sql: |
      SELECT o.*, c.region
      FROM source o
      LEFT JOIN customers c ON c.customer_id = o.customer_id
  - { phase: pre, derive: { field: order_total, sql: "amount + shipping_fee" } }
  - { phase: pre, filter: { sql: "status <> 'test'" } }

# ── QUALITY — correctness + completeness ─────────────────────────────────────
quality:
  enforce_required: true
  fail_pipeline_on_dataset_error: false
  row_rules:
    - { name: positive_amount, sql: "amount > 0" }
    - { not_null: order_id }
    - { accepted_values: { field: status, values: [placed, shipped, delivered, cancelled] } }
    - { range: { field: amount, min: 0 } }
  dataset_rules:
    - { name: order_id_unique, unique: order_id }
    - null_ratio: { field: customer_email, max: 0.02, category: completeness }

# ── SERVICE LEVELS — freshness, availability, volume ─────────────────────────
service_levels:
  freshness:    { threshold: "1h", field: ordered_at }
  availability: { threshold: 0.99 }
  row_count:    { min_rows: 1, max_rows: 10000000 }

# ── LINEAGE — provenance columns ─────────────────────────────────────────────
lineage:
  enabled: true
  capture_source_path: true
  capture_run_id: true

# ── MATERIALIZATION — where it lands ─────────────────────────────────────────
materialization:
  strategy: merge
  format: iceberg
  location: "s3://lakehouse/sales/silver_orders"
  partition_by: [region]

# ── SERVER — target/output connection context ───────────────────────────────
server:
  type: warehouse
  path: "s3://lakehouse/sales/silver_orders"
  mode: validate
  format: parquet
  cast_to_string: false
  post_ingestion: { action: retain }

# ── QUARANTINE — what happens to bad rows ────────────────────────────────────
quarantine:
  enabled: true
  include_error_reason: true
  fail_on_quarantine: false
  write_mode: append

# ── SCHEMA POLICY — drift handling ───────────────────────────────────────────
schema_policy:
  evolution: compatible
  unknown_fields: quarantine

# ── EDGES — mesh dependencies ────────────────────────────────────────────────
upstream: ["sales.orders.bronze_orders"]
downstream:
  - { type: dashboard, name: "Sales Daily", platform: tableau, owner: analytics@acme.com }

# ── COMPLIANCE — free-form classification & controls ─────────────────────────
compliance:
  regulations: [GDPR, CCPA]
  data_residency: eu-west
  retention: { period: 400d, basis: legal }
  classification: confidential

# ── OPERATIONS ───────────────────────────────────────────────────────────────
tier: gold
schedule: "0 * * * *"
```
