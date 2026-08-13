# Databricks

**Engine:** Spark (also Polars / DuckDB for external tables) · **Format:** Delta · **Storage:** Unity Catalog — managed, plus external ADLS · **Status:** ✅ Live — one-click UC bootstrap; external ADLS Delta written by Polars/DuckDB proven on a real workspace.

## The same contract

No change from the [canonical RideFlow contract](index.md#what-same-contract-means-here). Backend choices:

```yaml
materialization:
  strategy: merge
  format: delta          # Unity Catalog Delta
```

## Run it

Self-contained one-click bootstrap (serverless, `rideflow_demo` catalog, a Volume landing zone — no external storage account required):

```bash
# Reference repo: SaaS_lakelogic-demo-databricks-ridehailing
databricks bundle deploy && databricks bundle run rideflow_bootstrap
```

The full data-mesh repo (`lakelogic-databricks-data-mesh-lakehouse`) runs all six domains on a workspace with Unity Catalog.

## What it materializes

Delta tables in Unity Catalog — bronze → silver → gold — governed identically to every other backend (quality gates, quarantine, PII masking, lineage). SCD2 dimensions materialize as Delta merge/history.

## Beyond Spark: external Delta without a cluster

The same contracts have been proven writing **Spark-registered Unity Catalog *external* Delta tables on ADLS using Polars + DuckDB** — i.e. the governed medallion without a Spark cluster in the loop, then queryable through UC as normal. This is the "no-JVM" path on Databricks storage.

## Special configuration

- **Serverless-friendly:** the bootstrap uses serverless compute and a UC Volume for landing, so it runs with no long-lived cluster.
- **External tables:** for the Polars/DuckDB external-Delta path, the runtime writes Delta to `abfss://…` and the table is registered in UC as EXTERNAL. Running the deploy CLI as the workspace service principal (with the right grants) is required.
- **`.py` vs `.ipynb` in bundles:** Databricks Asset Bundles treat notebook source formats distinctly — keep the job source format consistent to avoid a sync-snapshot mismatch.
