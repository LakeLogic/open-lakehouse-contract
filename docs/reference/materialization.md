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

`strategy: scd2` keeps history with validity columns instead of overwriting. The
version key is the contract's `primary_key` — there is no separate business-key
setting inside the `scd2` block:

```yaml
primary_key: [customer_id]

materialization:
  strategy: scd2
  scd2:
    track_columns: [name, tier, address]   # change detection
    timestamp_field: updated_at            # SOURCE column holding the change date
    effective_from_field: effective_from   # names of the injected columns
    effective_to_field: effective_to
    current_flag_field: is_current
    version_column: _version
    effective_from_default: "1900-01-01"
    effective_to_default: "9999-12-31"
```

The framework injects the surrogate key + audit columns; [quality rules that reference them](quality.md#dataset-rules) are enforced at materialization, not validation.

### `scd2` keys

Every key is optional and has a default. The strict OLC v1 model rejects any key
not on this list, because an undeclared key is silently ignored — and the most
expensive case is a misspelled `track_columns`, which does not mean "no tracking"
but "compare every column", cutting a new version on every load.

**Injected column names** — these name columns in the *target* dimension; they do
not select source columns.

| Key | Default | Purpose |
|---|---|---|
| `surrogate_key` | `_sk` | Name of the injected surrogate-key column. |
| `surrogate_key_strategy` | `hash` | `hash` (deterministic, from `primary_key` + version start) or `uuid`. |
| `effective_from_field` | `effective_from` | Version-start column. |
| `effective_to_field` | `effective_to` | Version-end column. |
| `current_flag_field` | `is_current` | Boolean column marking the live row. |
| `version_column` | `_version` | 1-based version counter per key. |
| `change_reason_column` | `_change_reason` | Holds `initial_load`, or the comma-joined names of the columns that changed. |

**Change detection**

| Key | Default | Purpose |
|---|---|---|
| `track_columns` | *(none)* | Only open a new version when one of these columns actually changed. Omit it and **every** incoming row for a known key is treated as a change. |

**Aliased keys** — each group below is one setting with two accepted spellings.
Both are load-bearing for contracts already in the wild; neither is deprecated.

| Alias group | Which wins | Default | Purpose |
|---|---|---|---|
| `timestamp_field` · `change_date_field` | `timestamp_field` | the value of `effective_from_field` | The **source** column whose value is the change-event date. |
| `end_date_default` · `effective_to_default` | `end_date_default`, by key presence (an explicit `null` still wins) | `9999-12-31` | Sentinel written to the end column of an open row. |
| `start_date_default` · `effective_from_default` | `start_date_default`, by key presence | `1900-01-01` | Start date for an initial load, or a key's first appearance. |

**Other**

| Key | Default | Purpose |
|---|---|---|
| `default_effective_from` | *(current UTC time)* | Despite the name, **not** an alias of the start defaults: it is the value substituted for "now", used when the incoming data carries neither the effective-from column nor a usable change-date column, and to close rows superseded within a single batch. Pin it to make a load reproducible. |
| `merge_dedup_guard` | `false` | Deduplicate incoming rows by primary key (latest change-date wins) before applying SCD2. Some writer paths take this from the materialization-level `merge_dedup_guard` flag instead. |
| `unknown_member` | *(see below)* | Kimball unknown-member row. |

**`scd2.unknown_member`**

| Key | Default | Purpose |
|---|---|---|
| `enabled` | `true` | Inject the unknown-member row. (The Spark already-written-table path treats a missing value as `false`.) |
| `surrogate_key_value` | `-1` | Surrogate-key value for the unknown row. |
| `default_values` | `{}` | Column → value for the unknown row's remaining columns. |

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
