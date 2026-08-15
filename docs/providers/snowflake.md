# Snowflake

**Engine:** Snowflake SQL · **Format:** native Snowflake tables · **Storage:** Snowflake database · **Status:** ✅ Live.

**Reference data mesh lakehouse:** [`lakelogic-snowflake-data-mesh-lakehouse`](https://github.com/LakeLogic/lakelogic-snowflake-data-mesh-lakehouse) — the full runnable RideFlow mesh lives there: the self-deploying `bootstrap.sql` + `setup.sql`, the native Snowflake **Project** (notebooks + a Task DAG), and every table it materializes.

## The same contract

No change from the [canonical RideFlow contract](index.md#what-same-contract-means-here). Backend choices:

```yaml
materialization:
  strategy: merge        # native Snowflake tables; Iceberg deferred to Horizon
```

## Special configuration

How the LakeLogic framework adapts to this backend (handled for you):

- **Identifier casing:** Snowflake upper-cases unquoted identifiers, so the framework uses UPPERCASE casing and a matching dedup `sort_by` ordering to keep keys stable.
- **Type casts:** `TRY_CAST → TO_VARCHAR` and related casts are adapted for Snowflake SQL (part of the `snowflake-engine-fixes` on the reference framework).
- **Shared connection:** the engine sets a shared Snowflake connection so notebooks and tasks in the Project reuse one session.
- **Iceberg:** native Snowflake tables today; Iceberg tables are deferred to the Horizon path.
