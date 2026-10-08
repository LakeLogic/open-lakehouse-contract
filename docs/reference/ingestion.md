# Ingestion & Sources

Everything about *where the data comes from* lives under the `source` block (the `SourceConfig` model — 25 fields). One `source` describes what to read, how to read it incrementally, how to partition it, how to handle change-data-capture, and what to do with the input **after** it's ingested.

```yaml
source:
  type: <source kind>          # the only always-relevant field
  # ... kind-specific fields below ...
```

`type` selects the *kind* of source; the remaining fields are the knobs that kind uses. The sections below group them by kind, then by cross-cutting concern (load modes, partitioning, CDC, post-ingestion).

!!! abstract "Powered by"
    The `source` block is a **Pydantic** model, so every field here is type-validated on load. The reference framework reads each kind with the appropriate library: file/object-store reads via **polars** / **pyarrow** (and DuckDB's `httpfs` / `azure` extensions, or **s3fs** / **gcsfs** / **adlfs** for cloud paths); databases via their DB-API/JDBC driver; REST APIs via **[dlt](https://dlthub.com)**; streaming micro-batches via **PySpark** structured streaming (or the engine's incremental reader).

---

## Source kinds

| `type` | Reads | Key fields |
|---|---|---|
| `landing` | Files in a landing directory or object store (CSV, JSON, JSONL, Parquet) | `path`, `format`, `pattern` |
| `stream` | A file or table location read in micro-batches by watermark | `path`, `format`, `watermark_field` |
| `table` | An upstream lakehouse table (catalog name or `table:` reference) | `path`, `format` |
| `delta` | A Delta table directory | `path` |
| `iceberg` | An Iceberg table directory | `path` |
| `database` | A relational database, by query | `query`, `options`, `watermark_field` |
| `dlt` | An HTTP API or dlt verified source | `dlt` |
| `sftp` | Files on an SFTP server | `path`, `pattern`, `format`, `options` |


### Files / landing zone

Read files from a landing directory — the classic bronze source. Formats: `csv`, `tsv`, `json`, `ndjson` / `jsonl`,
`xml`, `xlsx` / `xls` / `excel`, `fixed_width`, `avro`, `parquet`; `.gz` and `.zip` files of any of them are read as well.

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
| `options` | How to read the format — see [Source options](#source-options). |

### Upstream lakehouse table

Read another governed table (the normal silver/gold source — a link in the mesh).

```yaml
source:
  type: table
  path: "table:catalog.schema.silver_orders"   # an upstream table reference
  format: delta                                 # delta | iceberg | ducklake | ...
```

`type: delta` and `type: iceberg` read a table directory by path (`path: "s3://lake/silver/orders/"`) without a catalog.

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
| `path` | The connection string, normally `env:VAR` so the password stays out of the contract. |
| `query` | The SQL to execute against the source (default: the whole `dataset` table). |
| `watermark_field` | Column used to fetch only new/changed rows (see [Load modes](#load-modes)). |
| `options` | `fetch_size`, partitioned reads, native CDC (`DatabaseOptions`); for a `mongodb://` path, `database`, `filter`, `projection`, `batch_size` (`MongoDbOptions`). |

A `mongodb://` or `mongodb+srv://` path reads a MongoDB-protocol collection (MongoDB, Atlas, Cosmos DB's MongoDB
API, DocumentDB); `dataset` is the collection and each document is one row.

### REST API and dlt sources

Ingest from an HTTP API or any [dlt](https://dlthub.com) verified source (`DltSourceConfig`). The source kind is `dlt`. There are two modes, chosen by which fields you set.

**Mode 1: verified source.** Name a dlt verified source and resource.

```yaml
source:
  type: dlt
  dlt:
    source: stripe_analytics          # dlt verified-source module
    resource: charges                 # resource within it
    credentials:
      api_key: "${STRIPE_API_KEY}"    # resolved from the environment at run time
```

**Mode 2: declarative REST API.** Declare the base URL and endpoints inline.

```yaml
source:
  type: dlt
  dlt:
    base_url: "https://api.example.com/v2/"
    write_disposition: merge          # append | replace | merge (default: replace)
    max_table_nesting: 2              # default: 1
    credentials: { token: "${API_TOKEN}" }   # from env, never inline in the repo
    endpoints:
      - name: orders
        path: "/orders"
        params: { status: "all" }
        paginator: cursor             # how the API pages results
```

| `DltSourceConfig` | Purpose |
|---|---|
| `source` / `resource` | Mode 1: the dlt verified source and resource to run. |
| `base_url` | Mode 2: API root. |
| `endpoints[]` | Mode 2: one `DltEndpointConfig` per endpoint: `name`, `path`, `params`, `paginator`. |
| `credentials` | Auth material. A value written as `${ENV_VAR}` is read from the environment. |
| `write_disposition` | `append` / `replace` / `merge`. |
| `max_table_nesting` | How deep to auto-unnest JSON responses. |

The reference framework needs the `dlt` extra (`pip install lakelogic[dlt]`).

### SFTP drop folder

Fetch files from an SFTP server, then validate them like any landing file.

```yaml
source:
  type: sftp
  path: "sftp://ingest@files.example.com:22/inbound/"   # user@host[:port]/remote-dir
  pattern: "orders_*.csv"          # glob within the remote dir (default: *)
  format: csv                      # csv | json | parquet (default: csv)
  load_mode: incremental           # only files modified since the last run
  options:
    private_key_path: ~/.ssh/id_ed25519
    known_hosts: ~/.ssh/known_hosts   # omit to verify against the default known_hosts
```

| Field | Purpose |
|---|---|
| `path` | `sftp://user@host[:port]/dir`. Port defaults to 22. A password in the URI is **rejected**: it would reach logs and run metadata. |
| `pattern` | Glob for files in the remote directory. |
| `format` | The file format; its [options](#source-options) are accepted alongside the SFTP ones. |
| `load_mode` | `incremental` downloads only files whose server mtime is newer than the last run's watermark. `full` reads every matching file. |
| `options.username` | Used when the URI has no user. |
| `options.password` / `options.private_key_path` | Authentication. Use one. A password must be `env:VAR` — a literal is rejected. |
| `options.known_hosts` | Host-key file. Omitted means the default `~/.ssh/known_hosts`. Only an explicit `known_hosts: null` turns verification off, and the reference framework warns when it does. |

Credentials can come from the environment instead of the contract:

| Variable | Replaces |
|---|---|
| `LAKELOGIC_SFTP_USER` | username (when neither the URI nor `options` has one) |
| `LAKELOGIC_SFTP_PASSWORD` | `options.password` |
| `LAKELOGIC_SFTP_KEY` | `options.private_key_path` |

### Kafka and Azure Event Hubs

`type: stream` with `options.kind` reads a message broker. Every micro-batch is validated and written, and the read
position is committed after each write, so the next run continues where the last one stopped. Messages must be JSON
objects; one that is not is quarantined with the reason and the stream continues.

```yaml
source:
  type: stream
  options:
    kind: kafka                        # kafka | eventhubs
    brokers: env:KAFKA_BROKERS         # host:port[,host:port]
    topic: rides
    starting_offsets: earliest         # earliest | latest — first run only
    trigger: available_now             # available_now (drain, then stop) | continuous
    security_protocol: SASL_SSL        # PLAINTEXT | SSL | SASL_PLAINTEXT | SASL_SSL
    sasl_mechanism: PLAIN
    sasl_username: my-user
    sasl_password: env:KAFKA_PASSWORD  # never a literal
```

`kind: eventhubs` needs only `connection_string: env:VAR`: the brokers and the SASL login come from it. Every key is
listed under `KafkaOptions` and `EventHubsOptions` in the generated reference.

### Streaming / micro-batch

A streaming source is a table/file source read in **micro-batches** driven by a watermark. The contract stays the same; the framework reads incrementally each trigger. Combine `load_mode: incremental` with a `watermark_field` and (optionally) a streaming engine on the framework side.

```yaml
source:
  type: stream
  path: "s3://bucket/events/"
  format: json
  load_mode: incremental
  watermark_field: event_time
  watermark_strategy: append          # how the watermark advances per batch
```

> The same governance (schema, quality, quarantine, PII, lineage) applies to every micro-batch. See the reference framework's `StreamSink` for the native structured-streaming path.

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

## Source options

`source.options` holds how to read the source. Which keys are allowed depends on the source, and an unknown key is
rejected with a suggestion (`header_rows` → "did you mean `header_row`?"):

| Source | Options | Keys |
|---|---|---|
| `format: csv` / `tsv` | `CsvOptions` | `delimiter`, `encoding`, `skip_rows`, `has_header`, `quote_char`, `null_values`, `comment_prefix` |
| `format: xlsx` / `xls` / `excel` | `ExcelOptions` | `sheet_name`, `header_row`, `skip_footer` |
| `format: json` / `ndjson` / `jsonl` | `JsonOptions` | `multiline` |
| `format: xml` | `XmlOptions` | `row_tag` |
| `format: fixed_width` | `FixedWidthOptions` | `columns`, `record_length`, `encoding`, `skip_rows`, `skip_footer`, `strip` |
| `format: avro` / `parquet` | `AvroOptions` / `ParquetOptions` | — |
| every file format | | `archive_member`, `implied_decimals`, `date_formats`, `decimal_comma` |
| `type: database` | `DatabaseOptions` / `MongoDbOptions` | see [Database](#database-sql-query) |
| `type: sftp` | `SftpOptions` + the format's | `username`, `password`, `private_key_path`, `known_hosts` |
| `type: stream` + `kind` | `KafkaOptions` / `EventHubsOptions` | see [Kafka and Azure Event Hubs](#kafka-and-azure-event-hubs) |

Every option has its meaning, default and an example in the generated reference (`skills/olc-reference.md`).

- **Settings live only under `options`.** `source.record_length` (or `encoding`, `skip_rows`, `skip_footer`, `strip`)
  is rejected with "`record_length` belongs under `source.options`".
- **Credentials are never written in a contract.** A key that holds a secret (`password`, `*_token`, `*_secret`,
  `connection_string`, …) must be an environment reference, `env:VAR` or `${ENV:VAR}`.
- **`engine_options`** is the one free-form corner: engine-specific extras, passed through unchecked.

## Every `source` field at a glance

`type`, `query`, `path`, `format`, `load_mode`, `pattern`, `watermark_field`, `cdc_op_field`, `cdc_delete_values`, `cdc_timestamp_field`, `dlt`, `partition`, `empty_behavior`, `watermark_strategy`, `target_path`, `lookback`, `from_date`, `to_date`, `pipeline_log_table`, `pipeline_name`, `manifest_path`, `watermark_date_parts`, `partition_filters`, `flatten_nested`, `post_ingestion`.
