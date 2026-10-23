# LakeLogic Core playbook — recipes

Generated from `recipes/` by `scripts/generate_reference.py`. Each recipe is a contract that
LakeLogic Core runs, proven against real systems. Copy the contract, then fill in every
`{parameter}`. Secrets are NEVER written into a contract: use `env:VAR` (or a key vault reference).

| Recipe | Group | Use when |
|---|---|---|
| Ingest a database table into the landing zone | ingest | A table in PostgreSQL, MySQL, SQL Server / Azure SQL, Oracle or SQLite should be copied into the lakehouse's landing zone as files, a full copy first and only new or changed rows after that. |

## Ingest a database table into the landing zone

`ingest-database-to-landing` · ingest · load patterns: full, incremental

A table in PostgreSQL, MySQL, SQL Server / Azure SQL, Oracle or SQLite should be copied into the lakehouse's landing zone as files, a full copy first and only new or changed rows after that.

```yaml
version: 1.0.0
dataset: '{source_table}'
info:
  title: '{source_table} from {source_system}'
  target_layer: bronze
  system: '{source_system}'
source:
  type: database
  path: env:SRC_DB_URL
  load_mode: incremental
  watermark_field: '{watermark_column}'
  options:
    fetch_size: '{fetch_size}'
model:
  fields:
  - name: id
    type: long
    required: true
    description: Replace with the table's own columns, or let Studio draft them from
      the table.
  - name: '{watermark_column}'
    type: timestamp
    description: When the row last changed; each run reads only rows newer than the
      last one read.
materialization:
  strategy: append
  target_path: '{landing_path}'
  format: parquet
metadata:
  run_log_table: '{run_log_table}'
```

| Parameter | What it is | Expected format | Example | Secret | Set in |
|---|---|---|---|---|---|
| `SRC_DB_URL` | How to connect to the source database. | `<dialect>://<user>:<password>@<host>:<port>/<database>` | `postgresql://ingest:****@pg-prod.postgres.database.azure.com:5432/sales?sslmode=require` | yes | environment variable (or a key vault secret exposed as one) |
| `source_table` | The table to copy, schema-qualified where the database needs it. | `<schema>.<table>` | `public.orders` | no | contract |
| `source_system` | The system the table belongs to; names the landing folder and the bronze table. | `snake_case name` | `erp` | no | contract |
| `watermark_column` | A column that grows when a row is added or changed, so later runs read only new rows. | `a timestamp or ever-increasing number column of the source table` | `updated_at` | no | contract |
| `landing_path` | The folder in the landing zone the files are written to, one folder per table. | `<landing_root>/<system>/<table>` | `abfss://landing@mystorage.dfs.core.windows.net/erp/orders` | no | _system.yaml environment ({landing_root}) — a different place per environment |
| `fetch_size` | Rows fetched per round trip to the database — how much the source serves at a time. | `a whole number of rows; size it to the row width and the database tier` | `10000` | no | contract (source.options.fetch_size) |
| `partition_column` | Optional — read in parallel slices of this column (Spark and Polars only). | `a numeric or date column with an index, e.g. the primary key` | `id` | no | contract (source.options.partition_column + partition_num), only when one connection is too slow |
| `run_log_table` | Where each run records how far it read (the watermark), so the next run starts there. | `<schema>.<table> on the platform; run_log_dir / run_log_path (a folder or JSON file) also work` | `lakelogic.run_logs` | no | contract — in a Studio project the project's _system.yaml sets it for every table |
| `storage login` | How the run signs in to the landing storage. | `AZURE_STORAGE_ACCOUNT + (AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID) or AZURE_STORAGE_ACCOUNT_KEY; AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY for S3` | `AZURE_STORAGE_ACCOUNT=mystorage` | yes | environment variables |

**Before you run**

- Set SRC_DB_URL where the pipeline runs (environment or key vault).
- Allow the pipeline's network address through the database firewall.
- Give the pipeline's identity write access to the landing folder.

**What a design-time test proves:** Studio checks the contract and runs it on generated rows written to a sandbox folder; it never connects to your database or writes to your landing zone. The first real run is yours.
