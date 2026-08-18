# MotherDuck

**Engine:** DuckDB · **Format:** DuckLake · **Storage:** MotherDuck-hosted catalog · **Status:** ✅ Live.

[MotherDuck](https://motherduck.com) is a **serverless analytics platform built on DuckDB** — more than hosted DuckDB. It adds **hybrid execution** (splitting a query between your laptop and the cloud), a managed cloud catalog with **zero-copy sharing**, a collaborative SQL UI, and elastic scale — all DuckDB-native. With DuckLake, your governed medallion runs from a laptop straight into a **MotherDuck-hosted lakehouse** — same contracts, no local files, no Spark.

**Reference data mesh lakehouse:** `lakelogic-motherduck-data-mesh-lakehouse` *(coming soon — repo is private for now)* — a deliberately thin, upload-and-run artifact: how to seed and build the mesh into MotherDuck, and every table it materializes.

## The same contract

Identical to the [DuckLake provider](duckdb-ducklake.md); only the catalog location changes (local file → MotherDuck):

```yaml
materialization:
  strategy: merge
  format: ducklake        # metadata target points at MotherDuck ('md:')
```

## Special configuration

How the LakeLogic framework adapts to this backend (handled for you):

- **Native DuckLake database, not ATTACH.** MotherDuck "workspace mode" rejects `ATTACH 'ducklake:md:…'`. The framework instead connects to `md:` and issues `CREATE DATABASE IF NOT EXISTS "<catalog>" (TYPE DUCKLAKE)`, then writes into it. The reference framework detects the MotherDuck backend automatically from an `md:` metadata path.
