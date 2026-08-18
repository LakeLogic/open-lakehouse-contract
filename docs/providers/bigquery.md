# BigQuery (GCP)

**Engine:** BigQuery (also Spark for Iceberg) · **Format:** BigQuery native tables, plus Iceberg on GCS · **Storage:** BigQuery datasets; Iceberg on Google Cloud Storage · **Status:** ✅ Live.

The same contracts run on **three execution surfaces**: a headless **Cloud Run Job** (the BigQuery engine, all 11 systems), a **BigQuery Pipelines** notebook DAG (assemble the medallion visually in the UI), and **Dataproc Serverless** Spark for **Iceberg** on GCS — one contract set, three ways to run it.

**Reference data mesh lakehouse:** `lakelogic-gcp-data-mesh-lakehouse` *(coming soon — repo is private for now)* — the full runnable RideFlow mesh lives there: all three execution surfaces, and every table it materializes (BigQuery native + 18 Iceberg tables on GCS).

## The same contract

No change from the [canonical RideFlow contract](index.md#what-same-contract-means-here) — RideFlow being the fictional ride-hailing company (like Uber) used throughout. Backend choices:

```yaml
materialization:
  strategy: merge        # BigQuery native tables (or Iceberg via the Spark path)
```

## Special configuration

The BigQuery engine carries a handful of real dialect fixes (all on the reference framework):

- **Backtick-quoted identifiers** and **case-insensitive column** resolution.
- **Client location** pinned so datasets and jobs co-locate.
- **`TEMP` tables need a session**; the engine opens one.
- **Rewrites:** `CONCAT_WS`, `TO_DATE`, and bare `UNION` are rewritten to BigQuery-standard SQL; `DOUBLE`/`FLOAT` type keywords and backslash escaping handled.
- **Loads** via `load_table_from_dataframe` with column dedup, complex-cell JSON encoding, and TIMESTAMP-based SCD2.
- **Patched engine delivery:** ships via a GCS wheel + app tarball, bootstrapped at runtime (no image rebuild).
