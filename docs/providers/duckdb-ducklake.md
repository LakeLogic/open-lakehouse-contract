# DuckDB / DuckLake

**Engine:** DuckDB · **Format:** DuckLake · **Storage:** local files, or S3 / GCS / Azure ADLS · **Status:** ✅ Live.

[DuckLake](https://ducklake.select) is DuckDB's open lakehouse format — a SQL-catalog (DuckDB / SQLite / Postgres) plus Parquet data. You get a real **ACID** lakehouse: snapshots & time-travel, schema evolution, hidden partitioning, data inlining for small tables, and concurrent writers (a Postgres catalog adds GRANT/REVOKE governance) — with **nothing to run**.

**Reference data mesh lakehouse:** `lakelogic-duckdb-ducklake-data-mesh-lakehouse` *(coming soon — repo is private for now)* — the full runnable RideFlow mesh lives there: how to seed and build it, and every table it materializes.

## The same contract

No change from the [canonical RideFlow contract](index.md#what-same-contract-means-here). The backend choices for this provider:

```yaml
materialization:
  strategy: merge
  format: ducklake        # ← the only backend-specific line
```

## Data on your cloud bucket

The contracts don't change — only where the Parquet lands. The metadata catalog stays local; the data goes to object storage:

```bash
python -m orchestration.run_mesh --data-path s3://my-bucket/rideflow      # AWS  S3
python -m orchestration.run_mesh --data-path gs://my-bucket/rideflow      # GCP  GCS
python -m orchestration.run_mesh --data-path az://mycontainer/rideflow    # Azure ADLS
```

Credentials come from each provider's default chain / standard env vars (AWS default chain + `AWS_REGION`; `GCS_KEY_ID`/`GCS_SECRET`; `AZURE_STORAGE_*`) — never on the command line, never in the repo.

## Special configuration

How the LakeLogic framework adapts to this backend (handled for you):

- **Reads are single-use views:** the framework materializes cross-domain links as real tables before a fact scans them twice (otherwise a second scan reads zero rows).
- **Identifier quoting:** contracts authored Databricks-style (backtick-quoted) are de-quoted on resolve so cross-domain marts bind on DuckDB.
