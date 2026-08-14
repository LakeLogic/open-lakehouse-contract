# Materialization & Storage

Materialization is **declarative convergence**: the contract declares the desired state of the target table, and the framework converges the actual table toward it. The `materialization` block (`Materialization`, 18 fields) chooses the write strategy, table format, partitioning, history handling, and delete semantics.

!!! abstract "Powered by"
    `Materialization` is a **Pydantic** model. The write goes through the format's library: **Delta** via **deltalake** (delta-rs) on DuckDB/Polars or **delta-spark** on **PySpark**; **Iceberg** via **pyiceberg** (+ a catalog such as Glue) or the Iceberg Spark framework; **DuckLake** via DuckDB's **`ducklake`** extension; plain Parquet via **pyarrow**.

## Shape

```yaml
materialization:
  strategy: merge            # append | merge | scd2 | overwrite
  format: iceberg            # delta | iceberg | ducklake | parquet | native
  location: "s3://lake/silver/orders"    # or target_path
  partition_by: [order_date]
  cluster_by: [customer_id]
  merge_dedup_guard: true
```

## Write strategies

| `strategy` | Converges the table to… |
|---|---|
| `append` | …all rows, added. |
| `merge` | …latest row per `primary_key` (upsert). |
| `scd2` | …full history — a slowly-changing dimension with validity windows. |
| `overwrite` | …exactly the current batch (replace). |

| Field | Purpose |
|---|---|
| `strategy` | The convergence semantics above. |
| `format` | Table format for the target. |
| `location` / `target_path` | Where the table is written. |
| `partition_by` | Physical partition columns. |
| `cluster_by` | Clustering/Z-order columns for read pruning. |
| `merge_dedup_guard` | Guard against duplicate keys within a merge batch. |
| `table_properties` | Format-specific table properties passed through to the writer. |
| `compaction` | Compaction/optimize settings for the table. |

## SCD2 history

`strategy: scd2` keeps history with validity columns instead of overwriting:

```yaml
materialization:
  strategy: scd2
  scd2:
    business_key: [customer_id]
    effective_from: valid_from
    effective_to: valid_to
    current_flag: is_current
    hash_columns: [name, tier, address]   # change detection
```

The framework injects the surrogate key + audit columns; [quality rules that reference them](quality.md#dataset-rules) are enforced at materialization, not validation.

## Facts & dimensions

`fact` (`FactConfig`) marks a table as a fact and declares milestone-date semantics (e.g. accumulating snapshot facts):

```yaml
materialization:
  fact:
    type: transaction        # transaction | periodic | accumulating
    milestone_dates: [requested_at, accepted_at, completed_at]
```

## Soft deletes

Rather than physically removing rows (e.g. from a [CDC delete](ingestion.md#change-data-capture-cdc)), mark them — preserving history and enabling audit:

```yaml
materialization:
  soft_delete_column: is_deleted
  soft_delete_value: true
  soft_delete_time_column: deleted_at
  soft_delete_reason_column: delete_reason
```

| Field | Purpose |
|---|---|
| `soft_delete_column` | Column set when a row is deleted. |
| `soft_delete_value` | The value written to mark a delete. |
| `soft_delete_time_column` | When the delete happened. |
| `soft_delete_reason_column` | Why (e.g. the CDC op or a rule). |

## Reprocessing

Bounded, idempotent re-runs over a date window — replace a slice without duplicating the rest:

```yaml
materialization:
  reprocess_policy: window          # how a reprocess replaces existing data
  reprocess_date_column: order_date
```

## Schema evolution

`schema_policy` (`SchemaPolicy`) governs how the target reacts when the incoming schema changes, and what to do with unexpected columns:

```yaml
schema_policy:
  evolution: compatible     # strict | append | merge | overwrite | compatible | all
  unknown_fields: quarantine   # quarantine | drop | allow
```

| Field | Values | Meaning |
|---|---|---|
| `evolution` | `strict` / `append` / `merge` / `overwrite` / `compatible` / `all` | How much schema change is tolerated on write. `strict` rejects any change; `compatible` allows safe additions; `all` allows anything. |
| `unknown_fields` | `quarantine` / `drop` / `allow` | What to do with columns not in the contract — route to quarantine, silently drop, or pass through. |

## Unknown dimension members

`unknown_member` configures the placeholder row used when a fact references a dimension key that doesn't exist yet (the classic `-1 / "Unknown"` member), so facts never lose rows to a missing lookup.
