# Transformation

Transformations are the declared steps between the source and the materialized target. Each entry in `transformations[]` is one operation (`Transformation`); they run in order. OLC is **SQL-first** — the `sql:` op gives you full SQL — and the shorthand ops below are convenience wrappers that compile to SQL for the routine cases. Mix and match freely.

!!! abstract "Powered by"
    Transformations are **Pydantic** models compiled to native operations on the active engine — DataFrame ops / SQL on **PySpark**, **duckdb**, or **polars**. The same declared step runs on every backend; `sql:` steps run in that engine's dialect (the runtime rewrites dialect differences).

## `phase` — pre or post

Every op accepts `phase: pre | post`. **Pre** transforms run before quality checks and may reference only source columns; **post** transforms run after the good/bad split and may reference derived columns too.

```yaml
transformations:
  - rename: { from: cust_id, to: customer_id }   # phase defaults sensibly per op
    phase: pre
```

---

## SQL-first (the escape hatch)

The most powerful op. Full SQL with access to `source` (the main dataset) and any `links:` reference datasets:

```yaml
- sql: |
    SELECT
      o.*,
      ROUND(o.quantity * o.unit_price * (1.0 - COALESCE(o.discount_pct, 0)), 2) AS line_total,
      c.name AS customer_name
    FROM source o
    LEFT JOIN customers c ON o.customer_id = c.customer_id
  phase: post
```

Everything below is shorthand for common cases; drop to `sql:` whenever it's clearer.

---

## Column shaping

### `select` — keep only these columns

```yaml
- select:
    columns: [customer_id, email, age, status]
  phase: pre
```

### `drop` — remove these columns

```yaml
- drop:
    columns: [internal_notes, temp_field]
  phase: pre
```

### `rename` — rename columns

```yaml
# single
- rename: { from: cust_id, to: customer_id }
  phase: pre

# many
- rename:
    mappings:
      cust_id: customer_id
      email_addr: email
      cust_status: status
  phase: pre
```

### `cast` — change column types

```yaml
- cast:
    columns:
      customer_id: long
      age: int
      created_at: timestamp
  phase: pre
```

### `derive` — add a computed column

```yaml
- derive:
    field: age_group
    sql: "CASE WHEN age < 25 THEN 'young' WHEN age < 65 THEN 'adult' ELSE 'senior' END"
  phase: post
# optional engine-specific overrides: sql_duckdb / sql_spark
```

### `coalesce` — first non-null across columns

```yaml
- coalesce:
    field: email
    sources: [primary_email, secondary_email, backup_email]
    default: "unknown@example.com"
    output: email
  phase: pre
```

### `map_values` — remap values via a lookup dict

```yaml
- map_values:
    field: status
    mapping: { A: ACTIVE, I: INACTIVE, P: PENDING }
    default: UNKNOWN
    output: status
  phase: pre
```

---

## String helpers

### `trim` — strip whitespace

```yaml
- trim:
    fields: [email, status]
    side: both              # both | left | right
  phase: pre
```

### `lower` / `upper` — case-fold columns

```yaml
- lower: { fields: [email, status] }
  phase: pre
- upper: { fields: [country_code] }
  phase: pre
```

### `split` — split a string into parts

```yaml
- split:
    field: tags
    delimiter: ","
    output: tag_array
  phase: pre
```

### `json_extract` — pull a field out of JSON/struct

```yaml
- json_extract:
    field: latitude          # output column
    source: location_coordinates
    path: "$.latitude"
    cast: float
  phase: post
```

---

## Rows & reshaping

### `filter` — keep rows matching a predicate

```yaml
- filter:
    sql: "customer_id IS NOT NULL AND email IS NOT NULL"
  phase: pre
```

### `deduplicate` — drop duplicates, keep the chosen row

```yaml
- deduplicate:
    "on": [customer_id]       # quote 'on' — it's a YAML keyword
    sort_by: [updated_at]
    order: desc               # keep most recent
  phase: pre
```

### `explode` — one row per array element

```yaml
- explode:
    field: tag_array
    output: tag
  phase: pre
```

### `date_range_explode` — expand a [start, end] range into daily rows

```yaml
- date_range_explode:
    output: snapshot_date
    start_col: creation_date
    end_col: deleted_at        # nullable → defaults to today
    interval: 1d
  phase: post
```

### `bucket` — assign rows to numeric bands

```yaml
- bucket:
    field: price_band          # output column
    source: listing_price
    bins:
      - { lt: 250000,  label: sub_250k }
      - { lt: 500000,  label: 250k_500k }
      - { lt: 1000000, label: 500k_1m }
    default: 1m_plus
  phase: post
# bin bounds: lt / lte / gt / gte / eq
```

### `date_diff` — difference between two dates

```yaml
- date_diff:
    field: listing_age_days    # output column
    from_col: creation_date
    to_col: event_date
    unit: days                 # days | hours | months
  phase: post
```

---

## Joins & lookups

### `lookup` — one field from a reference table

```yaml
- lookup:
    field: country_name        # output column
    reference: dim_countries   # a dataset declared in links:
    "on": country_code         # column in this dataset
    key: code                  # matching column in the reference
    value: name                # column to pull across
    default_value: Unknown
  phase: post
```

### `join` — multiple fields from a reference table

```yaml
- join:
    reference: dim_products    # declared in links:
    "on": product_id
    key: id
    fields: [product_name, category, price]
    type: left                 # left | inner | right | full
    prefix: "product_"
    defaults:
      product_name: Unknown Product
      category: Uncategorized
  phase: post
```

---

## Aggregation & pivots

### `rollup` — group-by aggregation

```yaml
- rollup:
    group_by: [customer_segment, country]
    aggregations:
      total_customers: "COUNT(*)"
      avg_age: "AVG(age)"
      total_revenue: "SUM(lifetime_value)"
    keys: customer_id          # track rollup lineage (which rows rolled up)
    distinct: true
  phase: post
```

### `pivot` — long → wide

```yaml
- pivot:
    id_vars: [customer_id]
    pivot_col: metric
    value_cols: [value]
    values: [clicks, impressions]
    agg: sum
    name_template: "{pivot_alias}"
  phase: post
```

### `unpivot` — wide → long

```yaml
- unpivot:
    id_vars: [customer_id]
    value_vars: [clicks, impressions]
    key_field: metric
    value_field: value
    include_nulls: false
  phase: post
```

---

## Full op list — one example each

| Op | Group | Minimal example |
|---|---|---|
| `select` | column | `select: { columns: [a, b] }` |
| `drop` | column | `drop: { columns: [tmp] }` |
| `rename` | column | `rename: { from: a, to: b }` |
| `cast` | column | `cast: { columns: { age: int } }` |
| `derive` | column | `derive: { field: t, sql: "a + b" }` |
| `coalesce` | column | `coalesce: { field: e, sources: [e1, e2], output: e }` |
| `map_values` | column | `map_values: { field: s, mapping: { A: ACTIVE }, default: UNK, output: s }` |
| `trim` | string | `trim: { fields: [e], side: both }` |
| `lower` | string | `lower: { fields: [e] }` |
| `upper` | string | `upper: { fields: [cc] }` |
| `split` | string | `split: { field: tags, delimiter: ",", output: arr }` |
| `json_extract` | string | `json_extract: { field: lat, source: loc, path: "$.lat", cast: float }` |
| `filter` | rows | `filter: { sql: "id IS NOT NULL" }` |
| `deduplicate` | rows | `deduplicate: { "on": [id], sort_by: [ts], order: desc }` |
| `explode` | rows | `explode: { field: arr, output: tag }` |
| `date_range_explode` | rows | `date_range_explode: { output: d, start_col: s, end_col: e, interval: 1d }` |
| `bucket` | rows | `bucket: { field: band, source: price, bins: [{lt: 100, label: lo}], default: hi }` |
| `date_diff` | rows | `date_diff: { field: age, from_col: a, to_col: b, unit: days }` |
| `lookup` | join | `lookup: { field: name, reference: dim, "on": code, key: code, value: name }` |
| `join` | join | `join: { reference: dim, "on": id, key: id, fields: [x], type: left }` |
| `rollup` | agg | `rollup: { group_by: [g], aggregations: { n: "COUNT(*)" } }` |
| `pivot` | agg | `pivot: { id_vars: [id], pivot_col: m, value_cols: [v], values: [a, b], agg: sum }` |
| `unpivot` | agg | `unpivot: { id_vars: [id], value_vars: [a, b], key_field: m, value_field: v }` |
| `sql` | any | `sql: "SELECT *, a+b AS c FROM source"` |

!!! tip "Keep transforms declarative where you can"
    Declarative ops are portable, introspectable, and agent-friendly — an AI agent can add a `rename` or `filter` and know exactly what changed. Reserve `sql:` for genuinely bespoke logic: fully supported, but opaque to tooling.
