# Ingestion & Sources

Everything about *where the data comes from* lives under the `source` block (the `SourceConfig` model — 25 fields). One `source` describes what to read, how to read it incrementally, how to partition it, how to handle change-data-capture, and what to do with the input **after** it's ingested.

```yaml
source:
  type: <source kind>          # the only always-relevant field
  # ... kind-specific fields below ...
```

`type` selects the *kind* of source; the remaining fields are the knobs that kind uses. The sections below group them by kind, then by cross-cutting concern (load modes, partitioning, CDC, post-ingestion).

!!! abstract "Powered by"
    The `source` block is a **Pydantic** model, so every field here is type-validated on load. The reference runtime reads each kind with the appropriate library: file/object-store reads via **polars** / **pyarrow** (and DuckDB's `httpfs` / `azure` extensions, or **s3fs** / **gcsfs** / **adlfs** for cloud paths); databases via their DB-API/JDBC driver; REST APIs via **[dlt](https://dlthub.com)**; streaming micro-batches via **PySpark** structured streaming (or the engine's incremental reader).

---

## Source kinds

### Files / landing zone

Read files from a landing directory — the classic bronze source. Formats: CSV, JSON, JSONL, Parquet.

```yaml
source:
  type: landing
  path: "s3://bucket/landing/orders/"    # or a local path, abfss://, gs://
  format: csv                            # csv | json | jsonl | parquet
  pattern: "*.csv"                       # glob to select files
  flatten_nested: true                   # explode nested JSON into columns (or a list of paths)
  empty_behavior: skip                   # skip | fail  — when no files match
```

| Field | Purpose |
|---|---|
| `path` | Root location of the input files. |
| `format` | File format to parse. |
| `pattern` | Glob for selecting files within `path`. |
| `flatten_nested` | `true` to flatten nested JSON, or a list of specific nested paths to flatten. |
| `manifest_path` | Read an explicit manifest of files instead of globbing. |
| `empty_behavior` | `skip` (no-op on empty input) or `fail`. |

### Upstream lakehouse table

Read another governed table (the normal silver/gold source — a link in the mesh).

```yaml
source:
  type: table
  path: "table:catalog.schema.silver_orders"   # an upstream table reference
  format: delta                                 # delta | iceberg | ducklake | ...
```

### Database / SQL query

Pull from a relational source by query.

```yaml
source:
  type: database
  query: "SELECT * FROM public.orders WHERE updated_at > :watermark"
  load_mode: incremental
  watermark_field: updated_at
```

| Field | Purpose |
|---|---|
| `query` | The SQL to execute against the source. |
| `watermark_field` | Column used to fetch only new/changed rows (see [Load modes](#load-modes)). |

### REST API (via dlt)

Ingest from an HTTP API using an embedded [dlt](https://dlthub.com) source — pagination, auth, and multiple endpoints declared inline (`DltSourceConfig`).

```yaml
source:
  type: api
  dlt:
    source: rest_api
    base_url: "https://api.example.com/v2/"
    write_disposition: merge          # append | replace | merge
    max_table_nesting: 2
    credentials: { token: "${API_TOKEN}" }   # from env, never inline in the repo
    endpoints:
      - name: orders
        path: "/orders"
        params: { status: "all" }
        paginator: cursor             # how the API pages results
```

| `DltSourceConfig` | Purpose |
|---|---|
| `source` / `resource` | The dlt source/resource to run. |
| `base_url` | API root. |
| `endpoints[]` | One `DltEndpointConfig` per endpoint: `name`, `path`, `params`, `paginator`. |
| `credentials` | Auth material (reference env vars — don't hard-code secrets). |
| `write_disposition` | `append` / `replace` / `merge`. |
| `max_table_nesting` | How deep to auto-unnest JSON responses. |

### Streaming / micro-batch

A streaming source is a table/file source read in **micro-batches** driven by a watermark. The contract stays the same; the runtime reads incrementally each trigger. Combine `load_mode: incremental` with a `watermark_field` and (optionally) a streaming engine on the runtime side.

```yaml
source:
  type: stream
  path: "s3://bucket/events/"
  format: json
  load_mode: incremental
  watermark_field: event_time
  watermark_strategy: append          # how the watermark advances per batch
```

> The same governance (schema, quality, quarantine, PII, lineage) applies to every micro-batch. See the reference runtime's `StreamSink` for the native structured-streaming path.

---

## Load modes

`load_mode` controls how much of the source is read each run.

```yaml
source:
  load_mode: incremental       # full | incremental
  watermark_field: updated_at
  watermark_strategy: append
  watermark_date_parts: [year, month, day]   # for date-partitioned watermarks
  lookback: "3d"               # re-read a trailing window to catch late data
  from_date: "2026-01-01"      # explicit bounds (backfill / bounded reprocess)
  to_date:   "2026-01-31"
```

| Field | Purpose |
|---|---|
| `load_mode` | `full` (read everything) or `incremental` (only new/changed). |
| `watermark_field` | The column the watermark tracks. |
| `watermark_strategy` | How the watermark advances (e.g. append-only vs upsert semantics). |
| `watermark_date_parts` | For date-part watermarks — the parts that form the boundary. |
| `lookback` | A trailing window re-read every run to capture late-arriving data. |
| `from_date` / `to_date` | Explicit bounds for backfills or bounded reprocessing. |
| `pipeline_log_table` / `pipeline_name` | Where the watermark/run state is persisted. |

!!! note "Incremental needs a persisted watermark"
    Incremental mode reads the last watermark from run state. Runners that read the whole input each time (e.g. a demo that reloads a landing zone) set `LAKELOGIC_SKIP_INCREMENTAL_CHECK=1` to bypass the watermark requirement.

---

## Change data capture (CDC)

When the source emits change events (insert/update/delete), OLC applies them as a CDC stream rather than a plain append.

```yaml
source:
  type: database
  load_mode: incremental
  cdc_op_field: op                       # column holding the operation
  cdc_delete_values: ["D", "delete"]     # values that mean "delete this row"
  cdc_timestamp_field: op_ts             # order events by this to resolve last-writer-wins
```

| Field | Purpose |
|---|---|
| `cdc_op_field` | The column that carries the change operation. |
| `cdc_delete_values` | Which values in that column represent a delete. |
| `cdc_timestamp_field` | Orders change events so the latest wins on merge. |

Deletes surfaced by CDC pair naturally with [soft-delete materialization](materialization.md#soft-deletes) so history is preserved rather than physically removed.

---

## Partitioned reads

For date-partitioned inputs, `SourcePartition` selects which partitions to read.

```yaml
source:
  partition:
    format: "year=%Y/month=%m/day=%d"    # partition path layout
    lookback_days: 3
    start_date: "2026-01-01"
    end_date: "2026-01-31"
    file_pattern: "*.parquet"
  partition_filters: { region: "eu" }    # additional predicate pushdown
```

---

## After ingestion: clean up the source

Once input is safely ingested, `post_ingestion` decides what happens to it — **including deleting or archiving the consumed files**. This is the "delete files once ingested" behavior; it has its own page because it's a lifecycle concern shared with the `server` block.

```yaml
source:
  post_ingestion:
    action: delete           # delete | archive | retain
    cleanup_is_blocking: false
    archive_path: "s3://bucket/archive/orders/"   # required when action: archive
```

→ Full detail in **[Post-Ingestion Lifecycle](lifecycle.md)**.

---

## Resilience

Transient source failures are retried per `RetryConfig`:

```yaml
source:
  retry: { max_attempts: 3, backoff: exponential, initial_delay: 2.0 }
```

## Every `source` field at a glance

`type`, `query`, `path`, `format`, `load_mode`, `pattern`, `watermark_field`, `cdc_op_field`, `cdc_delete_values`, `cdc_timestamp_field`, `dlt`, `partition`, `empty_behavior`, `watermark_strategy`, `target_path`, `lookback`, `from_date`, `to_date`, `pipeline_log_table`, `pipeline_name`, `manifest_path`, `watermark_date_parts`, `partition_filters`, `flatten_nested`, `post_ingestion`.
