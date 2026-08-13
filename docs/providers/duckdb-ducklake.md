# DuckDB / DuckLake

**Engine:** DuckDB · **Format:** DuckLake · **Storage:** local files, or S3 / GCS / Azure ADLS · **Status:** ✅ Live — full 6-domain RideFlow mesh, ~59 governed tables, zero infrastructure.

[DuckLake](https://ducklake.select) is DuckDB's open lakehouse format — a SQL-catalog (SQLite/DuckDB/Postgres) plus Parquet data, with snapshots and time-travel. It gives you a real ACID lakehouse with **nothing to run**.

## The same contract

No change from the [canonical RideFlow contract](index.md#what-same-contract-means-here). The backend choices for this provider:

```yaml
materialization:
  strategy: merge
  format: ducklake        # ← the only backend-specific line
```

## Run it

```bash
pip install lakelogic duckdb polars pyyaml
python -m orchestration.run_mesh          # seed + build the whole mesh into DuckLake
```

Reference repo: **`lakelogic-duckdb-ducklake-data-mesh-lakehouse`**.

## What it materializes

```
== DuckLake catalog summary ===================================
  rideflow_lake.marketing       11 tables
  rideflow_lake.marketplace     18 tables
  rideflow_lake.operations       6 tables
  rideflow_lake.payments         7 tables
  rideflow_lake.reference       13 tables
  rideflow_lake.shared           4 tables
  TOTAL                         59 tables

OK  11 systems - 59 tables - ~37s - DuckLake rideflow_lake
```

Inspect it with any DuckDB client — including DuckLake time-travel:

```sql
INSTALL ducklake; LOAD ducklake;
ATTACH 'ducklake:lakehouse/rideflow_lake.ducklake' AS rideflow_lake (DATA_PATH 'lakehouse/ducklake_data');
SELECT * FROM rideflow_lake.marketplace.gold_rideflow_fact_trip_daily_kpis LIMIT 20;
SELECT * FROM rideflow_lake.snapshots();     -- every write is a snapshot
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

- **Attach:** `ATTACH 'ducklake:<meta>.ducklake' AS <catalog> (DATA_PATH '<data>')`.
- **Reads are single-use views:** the runtime materializes cross-domain links as real tables before a fact scans them twice (otherwise a second scan reads zero rows).
- **Identifier quoting:** contracts authored Databricks-style (backtick-quoted) are de-quoted on resolve so cross-domain marts bind on DuckDB.
