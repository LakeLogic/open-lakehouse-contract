# AWS (Glue)

**Engine:** Spark (AWS Glue) · **Format:** Iceberg · **Storage:** Glue Data Catalog + S3 · **Status:** ✅ Live.

**Reference data mesh lakehouse:** `lakelogic-aws-data-mesh-lakehouse` *(coming soon — repo is private for now)* — the full runnable RideFlow mesh lives there: the Glue-job deploy, and the Glue-registered Iceberg tables it materializes on S3 (reference + marketplace domains; one Silver job is parked on Glue's Spark 3.5 — see below).

## The same contract

No change from the [canonical RideFlow contract](index.md#what-same-contract-means-here) — RideFlow being the fictional ride-hailing company (like Uber) used throughout. Backend choices:

```yaml
materialization:
  strategy: merge
  format: iceberg        # Glue Data Catalog-registered Iceberg on S3
```

## Special configuration

How the LakeLogic framework adapts to this backend (handled for you):

- **Catalog-registered Iceberg:** tables are registered in the Glue Data Catalog, not only written to a path — so Athena/Spark see them natively.
- **Plan-explosion fix:** on Spark, a merge that references a transformed frame in both an anti-join and a union duplicates lineage, and Catalyst's query plan grows super-linearly at compile time → driver OOM on tiny data. The framework **checkpoints before the merge** to cut the lineage, which resolves it.
- **Glue Spark 3.5 vs Spark 4:** the `silver_trips` job commits its data but its post-write step is marginal on Glue's Spark 3.5 (driver memory); the same job runs clean on Spark 4. It is the one ◑ item on an otherwise ✅ platform — called out rather than hidden.
