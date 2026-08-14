# Snowflake

**Engine:** Snowflake SQL · **Format:** native Snowflake tables · **Storage:** Snowflake database · **Status:** ✅ Live — the full RideFlow (like Uber) mesh runs green on a Snowflake trial, including a native Snowflake **Project** (notebooks + a Task DAG).

## The same contract

No change from the [canonical RideFlow contract](index.md#what-same-contract-means-here). Backend choices:

```yaml
materialization:
  strategy: merge        # native Snowflake tables; Iceberg deferred to Horizon
```

## Run it

Self-deploying from Git — `bootstrap.sql` + `setup.sql` create the objects, then the notebooks run FROM the repo root:

```sql
-- in a Snowflake worksheet
EXECUTE IMMEDIATE FROM @repo/bootstrap.sql;
EXECUTE IMMEDIATE FROM @repo/setup.sql;
```

Reference repo: **`lakelogic-snowflake-data-mesh-lakehouse`**.

## What it materializes

The full medallion across all six domains as native Snowflake tables, orchestrated by a **Task DAG** in a native Snowflake Project — bronze → silver → gold, with SCD2 dimensions synthesized in-warehouse. Governance (quality, quarantine, PII, lineage) is applied identically to every other backend.

## Special configuration

- **Identifier casing:** Snowflake upper-cases unquoted identifiers, so the framework uses UPPERCASE casing and a matching dedup `sort_by` ordering to keep keys stable.
- **Type casts:** `TRY_CAST → TO_VARCHAR` and related casts are adapted for Snowflake SQL (part of the `snowflake-engine-fixes` on the reference framework).
- **Shared connection:** the engine sets a shared Snowflake connection so notebooks and tasks in the Project reuse one session.
- **Trial accounts:** with no external-access integration on a trial, dependencies are staged as a wheelhouse rather than pulled from PyPI at runtime.
- **Iceberg:** native Snowflake tables today; Iceberg tables are deferred to the Horizon path.
