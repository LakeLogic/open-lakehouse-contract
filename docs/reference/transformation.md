# Transformation

Transformations are the declared steps between the source and the materialized target. Each entry in `transformations[]` is one operation (`Transformation`); they run in order. You can express most shaping declaratively — and drop to raw `sql` for anything bespoke.

!!! abstract "Powered by"
    Transformations are **Pydantic** models compiled to native operations on the active engine — DataFrame ops / SQL on **PySpark**, **duckdb**, or **polars**. The same declared step runs on every backend; `sql` steps are executed by that engine's SQL dialect (the runtime rewrites dialect differences).

## Shape

```yaml
transformations:
  - { rename: { old_name: new_name } }
  - { cast: { amount: double, order_date: date } }
  - derive:
      full_name: "concat(first_name, ' ', last_name)"
  - filter: "status != 'test'"
  - deduplicate: { keys: [order_id], order_by: updated_at desc }
  - { sql: "SELECT *, amount * 0.2 AS tax FROM {dataset}" }   # escape hatch
```

Every op also accepts a `phase` to control when it runs relative to validation/materialization.

## Column shaping

| Op | Does |
|---|---|
| `select` | Keep only the listed columns. |
| `drop` | Remove the listed columns. |
| `rename` | Rename columns (`{old: new}`). |
| `cast` | Change column types (`{col: type}`). |
| `derive` | Add computed columns from expressions. |
| `coalesce` | First non-null across columns → a target column. |
| `map_values` | Remap values via a lookup dict (with a default). |

## String helpers

| Op | Does |
|---|---|
| `trim` | Strip whitespace. |
| `lower` / `upper` | Case-fold columns. |
| `split` | Split a string column into parts (by delimiter). |
| `json_extract` | Pull fields out of a JSON/struct column into columns. |

## Rows & reshaping

| Op | Does |
|---|---|
| `filter` | Keep rows matching a predicate. |
| `deduplicate` | Drop duplicates by `keys`, keeping the row chosen by `order_by`. |
| `explode` | One row per element of an array column. |
| `date_range_explode` | Expand a `[start, end]` range into one row per date. |
| `bucket` | Assign rows to buckets/bins (fixed bins or edges). |
| `date_diff` | Compute the difference between two dates into a column. |

## Joins & lookups

| Op | Does |
|---|---|
| `join` | Join to another dataset (`left`/`inner`/… with `on` keys). |
| `lookup` | Enrich with columns from a reference dataset by key (a lightweight join). |

```yaml
transformations:
  - join:
      right: "table:catalog.silver.customers"
      how: left
      on: [customer_id]
      select: [customer_name, customer_tier]
  - lookup:
      reference: "table:catalog.reference.dim_city"
      key: city_code
      columns: [city_name, country]
```

## Aggregation & pivots

| Op | Does |
|---|---|
| `rollup` | Group-by aggregation (sum/avg/count/…) to a coarser grain. |
| `pivot` | Long → wide (values become columns). |
| `unpivot` | Wide → long (columns become rows). |

```yaml
transformations:
  - rollup:
      group_by: [city_code, kpi_date]
      aggregations:
        - { column: fare_amount, agg: sum, as: gross_revenue }
        - { column: trip_id, agg: count, as: trip_count }
```

## The SQL escape hatch

Anything the declarative ops don't cover, write directly. `{dataset}` refers to the current frame:

```yaml
transformations:
  - sql: |
      SELECT *,
             ntile(4) OVER (ORDER BY fare_amount) AS fare_quartile
      FROM {dataset}
```

## Full op list

`rename`, `derive`, `lookup`, `filter`, `deduplicate`, `select`, `drop`, `cast`, `trim`, `lower`, `upper`, `coalesce`, `split`, `explode`, `map_values`, `rollup`, `join`, `pivot`, `unpivot`, `json_extract`, `date_range_explode`, `bucket`, `date_diff`, `sql` — plus `phase` on any op.

!!! tip "Keep transforms declarative where you can"
    Declarative ops are portable, introspectable, and agent-friendly (an AI agent can add a `rename` or `filter` and know exactly what changed). Reserve `sql` for genuinely bespoke logic — it's fully supported, but opaque to tooling.
