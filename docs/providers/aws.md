# AWS (Glue)

**Engine:** Spark (AWS Glue) · **Format:** Iceberg · **Storage:** Glue Data Catalog + S3 · **Status:** ✅ Live — reference and marketplace domains materialize Glue-registered Iceberg on S3; one silver job is parked on Glue's Spark 3.5 (runs clean on Spark 4).

## The same contract

No change from the [canonical RideFlow contract](index.md#what-same-contract-means-here). Backend choices:

```yaml
materialization:
  strategy: merge
  format: iceberg        # Glue Data Catalog-registered Iceberg on S3
```

## Run it

Glue jobs (UI-visible pipelines) read landing CSVs from S3 and materialize Iceberg tables registered in the Glue Data Catalog:

```bash
# Reference repo: lakelogic-aws-data-mesh-lakehouse
aws configure --profile rideflow          # region eu-west-2
python deploy/run_mesh.py --profile rideflow
```

Data lands in `s3://rideflow-lakehouse-<account>/…`; tables appear in the Glue Data Catalog and are queryable from Athena.

## What it materializes

Glue-registered Iceberg tables for the reference and marketplace domains (bronze → silver → gold), governed identically to every other backend. The Iceberg tables are catalog-registered (via the Glue Catalog), not just path-based, so Athena/Spark see them natively.

## Special configuration

- **Catalog-registered Iceberg:** tables are registered in the Glue Data Catalog, not only written to a path.
- **Plan-explosion fix:** on Spark, a merge that references a transformed frame in both an anti-join and a union duplicates lineage, and Catalyst's query plan grows super-linearly at compile time → driver OOM on tiny data. The runtime **checkpoints before the merge** to cut the lineage, which resolves it.
- **Glue Spark 3.5 vs Spark 4:** the `silver_trips` job commits its data but its post-write step is marginal on Glue's Spark 3.5 (driver memory); the same job runs clean on Spark 4. It is the one ◑ item on an otherwise ✅ platform — called out rather than hidden.
- **Cost:** Glue is serverless Spark — no cluster to leave running.
