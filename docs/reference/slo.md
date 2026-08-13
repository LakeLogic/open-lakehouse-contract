# SLOs & Lineage

A data product isn't done when it materializes — it has to stay fresh, complete, and traceable. OLC declares **service-level objectives** (`service_levels`) and **lineage capture** (`lineage`) as first-class parts of the contract.

!!! abstract "Powered by"
    `ServiceLevel` and `LineageConfig` are **Pydantic** models. SLO checks run as engine queries (**PySpark** / **duckdb** / **polars**) after materialization; breaches raise [notifications](notifications.md). Lineage columns are injected into the output frame by the same engine, so provenance is physically present in every table.

## Service levels (SLOs)

```yaml
service_levels:
  freshness:
    threshold: "6h"           # data must be no older than 6 hours
    field: updated_at         # the column freshness is measured on
    description: "Orders land within 6h of the source event."
  availability: 0.999         # 99.9% of runs succeed
  row_count:
    min_rows: 1000
    max_rows: 5000000
    check_field: order_date
    skip_reprocess_days: 2
    description: "Daily volume sanity."
```

### `freshness` — `string | ServiceLevelObjective`

How recent the data must be. Shorthand as a duration string (`"6h"`), or the full form:

| `ServiceLevelObjective` | Purpose |
|---|---|
| `threshold` | The bound (a duration like `6h`, or a number). |
| `field` | The column measured against `now()`. |
| `description` | Human explanation, surfaced on breach. |

### `availability` — `number | ServiceLevelObjective`

The success-rate target (e.g. `0.999`), or a full objective with a description.

### `row_count` — `RowCountSLO`

Volume expectations, with reprocess-awareness:

| Field | Purpose |
|---|---|
| `min_rows` / `max_rows` | Acceptable row-count band. |
| `check_field` | Column scoping the count (e.g. per-day). |
| `skip_reprocess_days` | Don't alarm on recent days still being backfilled. |
| `description` | Human explanation. |

SLO breaches integrate with the SaaS control plane (incidents, dashboards) — the contract is where the target is *declared*; the runtime and platform are where it's *watched*.

## Lineage capture

`lineage` (`LineageConfig`, 21 fields) controls the provenance columns injected on every row. `enabled: true` turns on sensible defaults; every column is individually toggleable and renameable.

```yaml
lineage:
  enabled: true
  capture_source_path: true          # which file/table the row came from
  capture_timestamp: true            # when it was ingested
  capture_run_id: true               # the run that produced it
  capture_contract_name: true
  capture_domain: true
  capture_system: true
  capture_created_at: true
  capture_created_by: true
  created_by_override: "orders-pipeline"
  preserve_upstream: [source_system, ingested_at]   # carry upstream lineage through
  upstream_prefix: "src_"
```

### What you can capture

| Concern | Toggle | Column name field |
|---|---|---|
| Source path | `capture_source_path` | `source_column_name` |
| Ingest timestamp | `capture_timestamp` | `timestamp_column_name` |
| Run id | `capture_run_id` | `run_id_column_name` (`run_id_source`) |
| Contract name | `capture_contract_name` | `contract_name_column_name` |
| Domain / system | `capture_domain` / `capture_system` | `domain_column_name` / `system_column_name` |
| Created at / by | `capture_created_at` / `capture_created_by` | `created_at_column_name` / `created_by_column_name` |

### Preserving upstream lineage

`preserve_upstream` carries selected lineage columns from the source **through** the transformation, optionally prefixed with `upstream_prefix`, so a gold row can still name the bronze file it originated from. This is what makes [masking lineage-aware](security.md#masking-is-lineage-aware) and drift traceable end-to-end.

!!! note "Why lineage in the contract"
    Putting provenance in the contract (not an external catalog scan) means every row is *self-describing*: you can answer "where did this come from, which run, was it masked" from the data itself, on any platform, without a separate lineage service.
