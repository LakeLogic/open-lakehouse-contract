# Databricks

**Engine:** Spark (also Polars / DuckDB for external tables) · **Format:** Delta · **Storage:** Unity Catalog — managed, plus external ADLS · **Status:** ✅ Live.

**Reference data mesh lakehouse:** [`lakelogic-databricks-data-mesh-lakehouse`](https://github.com/LakeLogic/lakelogic-databricks-data-mesh-lakehouse) — the full runnable RideFlow mesh lives there: the one-click Unity Catalog bootstrap, how to build all six domains, and every Delta table it materializes.

## The same contract

No change from the [canonical RideFlow contract](index.md#what-same-contract-means-here) — RideFlow being the fictional ride-hailing company (like Uber) used throughout. Backend choices:

```yaml
materialization:
  strategy: merge
  format: delta          # Unity Catalog Delta
```

## Beyond Spark: external Delta without a cluster

The same contracts have been proven writing **Spark-registered Unity Catalog *external* Delta tables on ADLS using Polars + DuckDB** — i.e. the governed medallion without a Spark cluster in the loop, then queryable through UC as normal. This is the "no-JVM" path on Databricks storage.

## Special configuration

How the LakeLogic framework adapts to this backend (handled for you):

- **External tables:** for the Polars/DuckDB external-Delta path, the framework writes Delta to `abfss://…` and the table is registered in UC as EXTERNAL. Running the deploy CLI as the workspace service principal (with the right grants) is required.
- **`.py` vs `.ipynb` in bundles:** Databricks Asset Bundles treat notebook source formats distinctly — keep the job source format consistent to avoid a sync-snapshot mismatch.
