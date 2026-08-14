# BigQuery (GCP)

**Engine:** BigQuery (also Spark for Iceberg) · **Format:** BigQuery native tables, plus Iceberg on GCS · **Storage:** BigQuery datasets; Iceberg on Google Cloud Storage · **Status:** ✅ Live — 11/11 systems green on a real GCP project, via a Cloud Run Job; 18 Iceberg tables via Dataproc Serverless.

## The same contract

No change from the [canonical RideFlow contract](index.md#what-same-contract-means-here) — RideFlow being the fictional ride-hailing company (like Uber) used throughout. Backend choices:

```yaml
materialization:
  strategy: merge        # BigQuery native tables (or Iceberg via the Spark path)
```

## Run it

Three execution surfaces, same contracts:

- **Cloud Run Job** — the BigQuery engine runs the whole mesh headless (11/11 systems green).
- **BigQuery Pipelines notebook DAG** — assemble the medallion visually in the BigQuery UI.
- **Dataproc Serverless (Spark + Iceberg)** — materialize 18 Iceberg tables onto GCS.

Reference repo: **`lakelogic-gcp-data-mesh-lakehouse`**. The patched engine ships via a GCS wheel + app tarball, bootstrapped at runtime (no image rebuild).

## What it materializes

The full six-domain mesh as BigQuery native tables (Cloud Run / Pipelines path), and — via Dataproc Serverless Spark — 18 Iceberg tables on GCS. Governance is applied identically across both.

## Special configuration

The BigQuery engine carries a handful of real dialect fixes (all on the reference framework):

- **Backtick-quoted identifiers** and **case-insensitive column** resolution.
- **Client location** pinned so datasets and jobs co-locate.
- **`TEMP` tables need a session**; the engine opens one.
- **Rewrites:** `CONCAT_WS`, `TO_DATE`, and bare `UNION` are rewritten to BigQuery-standard SQL; `DOUBLE`/`FLOAT` type keywords and backslash escaping handled.
- **Loads** via `load_table_from_dataframe` with column dedup, complex-cell JSON encoding, and TIMESTAMP-based SCD2.
