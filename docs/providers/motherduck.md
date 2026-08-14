# MotherDuck

**Engine:** DuckDB · **Format:** DuckLake · **Storage:** MotherDuck-hosted catalog · **Status:** ✅ Live — marketplace domain, 18 governed tables + snapshots, on a real MotherDuck account.

[MotherDuck](https://motherduck.com) is cloud DuckDB. With DuckLake, your governed medallion runs from a laptop straight into a **MotherDuck-hosted lakehouse** — same contracts, no local files, no Spark.

## The same contract

Identical to the [DuckLake provider](duckdb-ducklake.md); only the catalog location changes (local file → MotherDuck):

```yaml
materialization:
  strategy: merge
  format: ducklake        # metadata target points at MotherDuck ('md:')
```

## Run it

```bash
pip install lakelogic duckdb polars pyyaml

echo "YOUR_TOKEN" > md_token.txt      # app.motherduck.com → Settings → Access Tokens (gitignored)
python run.py                         # seed locally, build the medallion in MotherDuck
```

Reference repo: **`lakelogic-motherduck-data-mesh-lakehouse`** — a deliberately thin co-marketing artifact.

## What it materializes

An 18-table `rideflow_lake` DuckLake database — RideFlow, a fictional ride-hailing company (like Uber) — on MotherDuck (the `marketplace` domain: bronze → silver → gold, SCD2 dims + facts), with DuckLake snapshots recorded per write. Inspect it in the MotherDuck UI or any DuckDB client:

```sql
USE rideflow_lake;
SHOW TABLES;
SELECT * FROM gold_rideflow_fact_trip_daily_kpis;
SELECT * FROM rideflow_lake.snapshots();      -- time-travel, hosted
```

## Special configuration

- **Native DuckLake database, not ATTACH.** MotherDuck "workspace mode" rejects `ATTACH 'ducklake:md:…'`. The framework instead connects to `md:` and issues `CREATE DATABASE IF NOT EXISTS "<catalog>" (TYPE DUCKLAKE)`, then writes into it. The reference framework detects the MotherDuck backend automatically from an `md:` metadata path.
- **Token handling.** The `motherduck_token` env var (or `md_token.txt`) is the only credential; it is gitignored and never committed.
