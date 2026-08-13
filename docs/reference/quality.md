# Validation & Quality

Quality is where an OLC earns "executable" — and, like transformations, it's **SQL-powered**. Every rule is a SQL predicate: a **row rule** is a `WHERE`-clause that a row must satisfy; a **dataset rule** is an aggregate query that must hold over the whole dataset. The shorthands (`not_null:`, `range:`, `accepted_values:`, …) are convenience wrappers that **compile to SQL**, so each is shown here **SQL variant first**.

> If you can write a SQL `WHERE` clause, you can write a quality rule. No Python, no custom code — just SQL.

!!! abstract "Powered by"
    Quality rules are **Pydantic** models; each rule's `sql` predicate is executed by the active engine — **PySpark** on Spark, **duckdb** on DuckDB, **polars** SQL on Polars — so a rule written once runs natively on every backend (the runtime rewrites dialect functions like `regexp_matches`). Failing rows route to the [quarantine](#quarantine).

## The shape

```yaml
quality:
  enforce_required: true                  # auto not_null rules for required fields
  fail_pipeline_on_dataset_error: false   # a failed dataset rule aborts the run
  row_rules: [ ... ]                       # per-row SQL predicates
  dataset_rules: [ ... ]                   # whole-dataset SQL assertions
```

| `Quality` field | Purpose |
|---|---|
| `enforce_required` | Auto-generate `not_null` rules for `required: true` fields. |
| `fail_pipeline_on_dataset_error` | Whether a dataset-rule failure aborts the pipeline. |
| `row_rules` | Rules evaluated per row; failing rows are quarantined. |
| `dataset_rules` | Rules evaluated over the whole (good) dataset. |

---

## Row rules

A row rule is a boolean SQL predicate — the row **passes** when it's true. The canonical form is `name` + `sql`; everything else is shorthand for a common predicate.

### Custom SQL (the canonical form)

```sql
email NOT LIKE '%@temp-mail.%' AND email NOT LIKE '%@disposable.%'
```
```yaml
- name: email_domain_valid
  sql: "email NOT LIKE '%@temp-mail.%' AND email NOT LIKE '%@disposable.%'"
  category: validity
  severity: error            # error (quarantine) | warning (log, keep) | info
  phase: pre                 # pre = source columns · post = derived columns
```

### `not_null`

```sql
email IS NOT NULL
```
```yaml
- not_null: email                                    # simple
- not_null: { fields: [email, status, created_at] }  # many
- not_null: { field: customer_id, name: customer_id_required, severity: error }
```

### `accepted_values`

```sql
status IN ('ACTIVE', 'INACTIVE', 'PENDING', 'SUSPENDED')
```
```yaml
- accepted_values: { field: status, values: [ACTIVE, INACTIVE, PENDING, SUSPENDED], category: consistency }
```

### `regex_match`

```sql
regexp_matches(email, '^[^@]+@[^@]+\.[^@]+$')
```
```yaml
- regex_match: { field: email, pattern: "^[^@]+@[^@]+\\.[^@]+$", category: correctness }
```

### `range`

```sql
age BETWEEN 18 AND 120        -- inclusive: true → BETWEEN; false → 18 < age < 120
```
```yaml
- range: { field: age, min: 18, max: 120, inclusive: true, category: correctness }
```

### `referential_integrity`

```sql
country_code IN (SELECT code FROM dim_countries)
```
```yaml
- referential_integrity: { field: country_code, reference: dim_countries, key: code, category: consistency }
```

### `lifecycle_window`

```sql
event_time >= current_date - INTERVAL 30 DAY     -- reject rows outside the recency window
```
```yaml
- lifecycle_window: { field: event_time, window: 30d }
```

### Numeric guardrails on a rule

Any `QualityRule` can attach numeric bounds instead of writing the comparison in SQL:

```yaml
- { name: amount_in_range,  sql: "true", must_be_between: [0, 100000] }
- { name: min_qty,          sql: "true", must_be_greater_than: 0 }
- { name: max_qty,          sql: "true", must_be_less_than: 1000 }
```

| `QualityRule` field | Purpose |
|---|---|
| `name` **(req)** | Rule identifier (shown in quarantine + logs). |
| `sql` **(req)** | Boolean predicate; row passes when true. |
| `severity` | `error` (quarantine) · `warning` (log, keep row) · `info` (log only). |
| `category` | Free-form tag (validity, completeness, consistency…). |
| `description` | Human explanation, surfaced on failure. |
| `phase` | `pre` (source columns) or `post` (derived columns) — see [Execution Order](execution-order.md). |
| `must_be_between` / `must_be_less_than` / `must_be_greater_than` | Numeric bounds as an alternative to SQL. |

---

## Dataset rules

A dataset rule is an **aggregate** SQL assertion over the whole good dataset — it must evaluate true.

### Custom SQL (the canonical form)

```sql
SELECT SUM(CASE WHEN status = 'ACTIVE' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) FROM source
```
```yaml
- name: active_customer_ratio
  sql: "SELECT SUM(CASE WHEN status = 'ACTIVE' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) FROM source"
  must_be_greater_than: 0.60
  category: validity
```

### `unique`

```sql
SELECT COUNT(*) = COUNT(DISTINCT customer_id) FROM source
```
```yaml
- unique: customer_id
- unique: { field: email, name: email_unique, severity: error }
```

### `null_ratio`

```sql
SELECT COUNT(*) FILTER (WHERE phone IS NULL) * 1.0 / COUNT(*) <= 0.20 FROM source
```
```yaml
- null_ratio: { field: phone, max: 0.20, category: completeness }
```

### `row_count_between`

```sql
SELECT COUNT(*) BETWEEN 1000 AND 10000000 FROM source
```
```yaml
- row_count_between: { min: 1000, max: 10000000, category: completeness }
```

!!! note "Rules that reference injected columns"
    A dataset rule may reference a column that materialization injects later (a surrogate key, SCD2 audit columns). At validation time that column doesn't exist yet and such keys are unique by construction — the runtime treats a "column not found" bind as *not-evaluated-here* (enforced at materialization), not an error.

---

## Field-level rules

Rules can also travel **with a field** in `model.fields[]`, so validity lives next to the column it constrains — still SQL under the hood:

```yaml
model:
  fields:
    - name: status
      type: string
      accepted_values: [new, paid, shipped, cancelled]
      rules:
        - { name: status_lower, sql: "status = lower(status)" }
    - { name: amount, type: float, min: 0, max: 100000 }
    - { name: email, type: string, max_length: 320 }
```

See [Security & PII](security.md) for the governance fields on `model.fields[]` (`pii`, `masking`, …).

---

## When rules run (pre vs post)

Row rules default to **pre** (validate source columns before the good/bad split); mark a rule `phase: post` to validate **derived** columns produced by post-transforms. The full sequence is on the [Execution Order](execution-order.md) page:

```
pre-transforms → PRE quality rules → good/bad split → post-transforms → POST quality rules
```

- **Pre** rules can reference only source columns.
- **Post** rules can reference source **and** derived columns.
- Errors are tagged `[pre]` / `[post]` in the error column for traceability.

---

## Severity

| Severity | Behaviour |
|---|---|
| `error` | Quarantine the row (default) — bad data never reaches downstream. |
| `warning` | Log the issue, keep the row — data flows, team is alerted. |
| `info` | Log only, no action — observability. |

---

## Quarantine

Failing rows aren't dropped — they're written to a **quarantine** table *with the failed rule and reason*, so nothing is lost and every rejection is auditable (`Quarantine` model).

```yaml
quarantine:
  enabled: true
  target: "s3://quarantine-bucket/customers"   # or table / location
  format: parquet                              # parquet | csv | delta | iceberg | ducklake | json
  write_mode: append                           # append | overwrite
  include_error_reason: true                   # attach the failing rule + message per row
  fail_on_quarantine: false                    # true → any quarantined row fails the run
  notifications_enabled: true
  strict_notifications: false
  notifications: [ ... ]                        # see Notifications
```

| `Quarantine` field | Purpose |
|---|---|
| `enabled` | Turn quarantine on/off. |
| `target` / `table` / `location` | Where quarantined rows go (named table or path). |
| `format` | Table format for the quarantine sink. |
| `write_mode` | How rows are written (append/overwrite). |
| `include_error_reason` | Attach the failing rule name + reason to each row. |
| `fail_on_quarantine` | Escalate: any quarantined row aborts the run. |
| `notifications_enabled` / `strict_notifications` | Emit alerts on quarantine events. |
| `notifications` | A list of `Notification` targets — see **[Notifications](notifications.md)**. |
