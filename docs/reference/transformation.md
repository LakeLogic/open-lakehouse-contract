# Transformation

Transformations are the declared steps between the source and the materialized target. Each entry in `transformations[]` is one operation (`Transformation`); they run in order. OLC is **SQL-first**: the `sql:` op gives you full SQL, and every shorthand op below is a convenience wrapper that **compiles to SQL**. So each op here shows its **SQL variant first** — that's what actually runs — followed by the shorthand you can use instead.

!!! abstract "Powered by"
    Transformations are **Pydantic** models compiled to native operations on the active engine — DataFrame ops / SQL on **PySpark**, **duckdb**, or **polars**. The SQL below is shown DuckDB-flavored for concreteness; the framework rewrites dialect differences (e.g. `QUALIFY`, `DATE_DIFF`, `PIVOT`) per engine, so the *same* op runs everywhere. In every `sql:` block, `source` is the current dataset and `links:` datasets are joinable by name.

!!! info "SQL is the portability bet — dialects are a v-next concern"
    OLC is SQL-native on purpose: `sql: "amount > 0"` is far more portable across engines than a bespoke `{ check: greater_than, value: 0 }` object, because Spark SQL, DuckDB, Snowflake, BigQuery, and Fabric all understand broadly SQL-shaped expressions. Dialect differences are real but bounded — today the reference framework rewrites the common ones. A future spec version may let a rule pin its dialect explicitly, e.g. `expression: { sql: "amount > 0", dialect: ansi }`, so authors can opt into a portable ANSI subset or an engine-specific escape hatch. **v1 does not try to solve every dialect** — write standard-leaning SQL, and let the framework handle the rest.

## `phase` — pre or post

Every op accepts `phase: pre | post`. **Pre** transforms run before quality checks and may reference only source columns; **post** transforms run after the good/bad split and may reference derived columns too. The full run sequence — where pre and post sit relative to validation, quarantine, and materialization — is on the [Execution Order](execution-order.md) page.

---

## SQL-first (the escape hatch)

The most powerful op — full SQL with access to `source` and any `links:` reference datasets. Everything below is shorthand for common shapes of this:

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

---

## Column shaping

### `select` — keep only these columns

```sql
SELECT customer_id, email, age, status FROM source
```
```yaml
- select: { columns: [customer_id, email, age, status] }
  phase: pre
```

### `drop` — remove these columns

```sql
SELECT * EXCLUDE (internal_notes, temp_field) FROM source
```
```yaml
- drop: { columns: [internal_notes, temp_field] }
  phase: pre
```

### `rename` — rename columns

```sql
SELECT * RENAME (cust_id AS customer_id, email_addr AS email, cust_status AS status) FROM source
```
```yaml
- rename: { from: cust_id, to: customer_id }          # single
  phase: pre
- rename:                                             # many
    mappings: { cust_id: customer_id, email_addr: email, cust_status: status }
  phase: pre
```

### `cast` — change column types

```sql
SELECT * REPLACE (
  CAST(customer_id AS BIGINT) AS customer_id,
  CAST(age AS INTEGER)        AS age,
  CAST(created_at AS TIMESTAMP) AS created_at
) FROM source
```
```yaml
- cast: { columns: { customer_id: long, age: int, created_at: timestamp } }
  phase: pre
```

### `derive` — add a computed column

```sql
SELECT *,
       CASE WHEN age < 25 THEN 'young' WHEN age < 65 THEN 'adult' ELSE 'senior' END AS age_group
FROM source
```
```yaml
- derive: { field: age_group, sql: "CASE WHEN age < 25 THEN 'young' WHEN age < 65 THEN 'adult' ELSE 'senior' END" }
  phase: post
# optional engine-specific overrides: sql_duckdb / sql_spark
```

### `coalesce` — first non-null across columns

```sql
SELECT *,
       COALESCE(primary_email, secondary_email, backup_email, 'unknown@example.com') AS email
FROM source
```
```yaml
- coalesce: { field: email, sources: [primary_email, secondary_email, backup_email], default: "unknown@example.com", output: email }
  phase: pre
```

### `map_values` — remap values via a lookup dict

```sql
SELECT *,
       CASE status WHEN 'A' THEN 'ACTIVE' WHEN 'I' THEN 'INACTIVE' WHEN 'P' THEN 'PENDING' ELSE 'UNKNOWN' END AS status
FROM source
```
```yaml
- map_values: { field: status, mapping: { A: ACTIVE, I: INACTIVE, P: PENDING }, default: UNKNOWN, output: status }
  phase: pre
```

---

## String helpers

### `trim` — strip whitespace

```sql
SELECT *, TRIM(email) AS email, TRIM(status) AS status FROM source   -- side: left→LTRIM, right→RTRIM
```
```yaml
- trim: { fields: [email, status], side: both }        # both | left | right
  phase: pre
```

### `lower` / `upper` — case-fold columns

```sql
SELECT *, LOWER(email) AS email, LOWER(status) AS status FROM source
SELECT *, UPPER(country_code) AS country_code FROM source
```
```yaml
- lower: { fields: [email, status] }
  phase: pre
- upper: { fields: [country_code] }
  phase: pre
```

### `split` — split a string into parts

```sql
SELECT *, STRING_SPLIT(tags, ',') AS tag_array FROM source
```
```yaml
- split: { field: tags, delimiter: ",", output: tag_array }
  phase: pre
```

### `json_extract` — pull a field out of JSON/struct

```sql
SELECT *, CAST(json_extract_string(location_coordinates, '$.latitude') AS FLOAT) AS latitude FROM source
```
```yaml
- json_extract: { field: latitude, source: location_coordinates, path: "$.latitude", cast: float }
  phase: post
```

---

## Rows & reshaping

### `filter` — keep rows matching a predicate

```sql
SELECT * FROM source WHERE customer_id IS NOT NULL AND email IS NOT NULL
```
```yaml
- filter: { sql: "customer_id IS NOT NULL AND email IS NOT NULL" }
  phase: pre
```

### `deduplicate` — drop duplicates, keep the chosen row

```sql
SELECT * FROM source
QUALIFY ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY updated_at DESC) = 1
```
```yaml
- deduplicate: { "on": [customer_id], sort_by: [updated_at], order: desc }   # quote 'on' (YAML keyword)
  phase: pre
```

`sort_by` is **required**. A deduplicate discards rows, so which duplicate survives
is a business decision the contract must state; without it an implementation has to
invent a survivor, and different engines invent different ones — the same contract
would then produce different tables on different platforms. A contract omitting it
is refused (conformance case `OLC-T-002`).

Order by the column that identifies the newest *record version* (`updated_at`), not
a business-event column: duplicates are usually re-deliveries of one row, and the
event columns are identical across them.

> **Deprecated:** `deduplicate_by_latest: { key_columns, timestamp_column }` is
> exactly `deduplicate` with `sort_by: [timestamp_column], order: desc`. It adds no
> expressiveness — it cannot express "keep the earliest" or a multi-column
> tie-break — and its separate `timestamp_column` spelling is silently ignored if
> written on `deduplicate`. It still parses for contracts already published; use
> `deduplicate` in new work.

### `explode` — one row per array element

```sql
SELECT *, UNNEST(tag_array) AS tag FROM source
```
```yaml
- explode: { field: tag_array, output: tag }
  phase: pre
```

### `date_range_explode` — expand a [start, end] range into daily rows

```sql
SELECT *,
       UNNEST(generate_series(creation_date, COALESCE(deleted_at, current_date), INTERVAL 1 DAY)) AS snapshot_date
FROM source
```
```yaml
- date_range_explode: { output: snapshot_date, start_col: creation_date, end_col: deleted_at, interval: 1d }
  phase: post
```

### `bucket` — assign rows to numeric bands

```sql
SELECT *,
       CASE WHEN listing_price < 250000  THEN 'sub_250k'
            WHEN listing_price < 500000  THEN '250k_500k'
            WHEN listing_price < 1000000 THEN '500k_1m'
            ELSE '1m_plus' END AS price_band
FROM source
```
```yaml
- bucket:
    field: price_band
    source: listing_price
    bins:
      - { lt: 250000,  label: sub_250k }
      - { lt: 500000,  label: 250k_500k }
      - { lt: 1000000, label: 500k_1m }
    default: 1m_plus                     # bin bounds: lt / lte / gt / gte / eq
  phase: post
```

### `date_diff` — difference between two dates

```sql
SELECT *, DATE_DIFF('day', creation_date, event_date) AS listing_age_days FROM source
```
```yaml
- date_diff: { field: listing_age_days, from_col: creation_date, to_col: event_date, unit: days }   # days | hours | months
  phase: post
```

---

## Joins & lookups

### `lookup` — one field from a reference table

```sql
SELECT s.*, COALESCE(d.name, 'Unknown') AS country_name
FROM source s
LEFT JOIN dim_countries d ON s.country_code = d.code
```
```yaml
- lookup: { field: country_name, reference: dim_countries, "on": country_code, key: code, value: name, default_value: Unknown }
  phase: post
```

### `join` — multiple fields from a reference table

```sql
SELECT s.*,
       COALESCE(d.product_name, 'Unknown Product') AS product_product_name,
       COALESCE(d.category, 'Uncategorized')       AS product_category,
       d.price                                     AS product_price
FROM source s
LEFT JOIN dim_products d ON s.product_id = d.id
```
```yaml
- join:
    reference: dim_products
    "on": product_id
    key: id
    fields: [product_name, category, price]
    type: left                           # left | inner | right | full
    prefix: "product_"
    defaults: { product_name: Unknown Product, category: Uncategorized }
  phase: post
```

---

## Aggregation & pivots

### `rollup` — group-by aggregation

```sql
SELECT customer_segment, country,
       COUNT(*)            AS total_customers,
       AVG(age)            AS avg_age,
       SUM(lifetime_value) AS total_revenue
FROM source
GROUP BY customer_segment, country
```
```yaml
- rollup:
    group_by: [customer_segment, country]
    aggregations: { total_customers: "COUNT(*)", avg_age: "AVG(age)", total_revenue: "SUM(lifetime_value)" }
    keys: customer_id                    # track rollup lineage (which rows rolled up)
    distinct: true
  phase: post
```

### `pivot` — long → wide

```sql
PIVOT source ON metric USING sum(value) GROUP BY customer_id   -- values: clicks, impressions
```
```yaml
- pivot: { id_vars: [customer_id], pivot_col: metric, value_cols: [value], values: [clicks, impressions], agg: sum, name_template: "{pivot_alias}" }
  phase: post
```

### `unpivot` — wide → long

```sql
UNPIVOT source ON clicks, impressions INTO NAME metric VALUE value   -- id_vars kept automatically
```
```yaml
- unpivot: { id_vars: [customer_id], value_vars: [clicks, impressions], key_field: metric, value_field: value, include_nulls: false }
  phase: post
```

---

## Full op list — SQL variant + shorthand

| Op | SQL variant (what runs) | Shorthand |
|---|---|---|
| `select` | `SELECT a, b FROM source` | `select: { columns: [a, b] }` |
| `drop` | `SELECT * EXCLUDE (tmp) FROM source` | `drop: { columns: [tmp] }` |
| `rename` | `SELECT * RENAME (a AS b) FROM source` | `rename: { from: a, to: b }` |
| `cast` | `SELECT * REPLACE (CAST(age AS INT) AS age) FROM source` | `cast: { columns: { age: int } }` |
| `derive` | `SELECT *, a + b AS t FROM source` | `derive: { field: t, sql: "a + b" }` |
| `coalesce` | `SELECT *, COALESCE(e1, e2) AS e FROM source` | `coalesce: { field: e, sources: [e1, e2], output: e }` |
| `map_values` | `SELECT *, CASE s WHEN 'A' THEN 'ACTIVE' END AS s FROM source` | `map_values: { field: s, mapping: { A: ACTIVE }, output: s }` |
| `trim` | `SELECT *, TRIM(e) AS e FROM source` | `trim: { fields: [e], side: both }` |
| `lower` | `SELECT *, LOWER(e) AS e FROM source` | `lower: { fields: [e] }` |
| `upper` | `SELECT *, UPPER(cc) AS cc FROM source` | `upper: { fields: [cc] }` |
| `split` | `SELECT *, STRING_SPLIT(tags, ',') AS arr FROM source` | `split: { field: tags, delimiter: ",", output: arr }` |
| `json_extract` | `SELECT *, CAST(json_extract_string(loc, '$.lat') AS FLOAT) AS lat FROM source` | `json_extract: { field: lat, source: loc, path: "$.lat", cast: float }` |
| `filter` | `SELECT * FROM source WHERE id IS NOT NULL` | `filter: { sql: "id IS NOT NULL" }` |
| `deduplicate` | `... QUALIFY ROW_NUMBER() OVER (PARTITION BY id ORDER BY ts DESC) = 1` | `deduplicate: { "on": [id], sort_by: [ts], order: desc }` |
| `explode` | `SELECT *, UNNEST(arr) AS tag FROM source` | `explode: { field: arr, output: tag }` |
| `date_range_explode` | `SELECT *, UNNEST(generate_series(s, e, INTERVAL 1 DAY)) AS d FROM source` | `date_range_explode: { output: d, start_col: s, end_col: e, interval: 1d }` |
| `bucket` | `SELECT *, CASE WHEN price < 100 THEN 'lo' ELSE 'hi' END AS band FROM source` | `bucket: { field: band, source: price, bins: [{lt: 100, label: lo}], default: hi }` |
| `date_diff` | `SELECT *, DATE_DIFF('day', a, b) AS age FROM source` | `date_diff: { field: age, from_col: a, to_col: b, unit: days }` |
| `lookup` | `SELECT s.*, d.name FROM source s LEFT JOIN dim d ON s.code = d.code` | `lookup: { field: name, reference: dim, "on": code, key: code, value: name }` |
| `join` | `SELECT s.*, d.x FROM source s LEFT JOIN dim d ON s.id = d.id` | `join: { reference: dim, "on": id, key: id, fields: [x], type: left }` |
| `rollup` | `SELECT g, COUNT(*) AS n FROM source GROUP BY g` | `rollup: { group_by: [g], aggregations: { n: "COUNT(*)" } }` |
| `pivot` | `PIVOT source ON m USING sum(v) GROUP BY id` | `pivot: { id_vars: [id], pivot_col: m, value_cols: [v], values: [a, b], agg: sum }` |
| `unpivot` | `UNPIVOT source ON a, b INTO NAME m VALUE v` | `unpivot: { id_vars: [id], value_vars: [a, b], key_field: m, value_field: v }` |
| `sql` | *(any SQL you write)* | `sql: "SELECT *, a+b AS c FROM source"` |

!!! tip "Shorthand or SQL — same result"
    The shorthand ops are portable, introspectable, and agent-friendly (an agent can add a `rename` and know exactly what changed). The `sql:` op is the full-power escape hatch. Because the shorthands *compile to the SQL shown above*, you can start with shorthand and drop to `sql:` the moment a case gets bespoke — no rewrite of the rest.
