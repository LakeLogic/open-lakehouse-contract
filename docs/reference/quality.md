# Validation & Quality

Quality is where an OLC earns "executable." Rules declared here are **run** against the data every time — rows that fail are quarantined (with the rule + reason), and dataset-level failures can fail the pipeline. The `quality` block is the `Quality` model.

!!! abstract "Powered by"
    Quality rules are **Pydantic** models. Each rule's `sql` predicate is executed by the active engine — **PySpark** on Spark, **duckdb** on DuckDB, **polars** SQL on Polars — so a rule written once runs natively on every backend. Failing rows route to the [quarantine](#quarantine).

## The shape

```yaml
quality:
  enforce_required: true                  # required fields must be present + non-null
  fail_pipeline_on_dataset_error: true    # a failed dataset rule aborts the run
  row_rules: [ ... ]                       # per-row predicates
  dataset_rules: [ ... ]                   # whole-dataset assertions
```

| `Quality` field | Purpose |
|---|---|
| `enforce_required` | Enforce `required: true` fields from the schema. |
| `fail_pipeline_on_dataset_error` | Whether a dataset-rule failure aborts the pipeline. |
| `row_rules` | Rules evaluated per row; failing rows are quarantined. |
| `dataset_rules` | Rules evaluated over the whole dataset (uniqueness, counts, null ratios). |

## Row rules

The general form is a named SQL predicate (`QualityRule`) — the row **passes** when the SQL is true:

```yaml
row_rules:
  - name: positive_amount
    sql: "amount > 0"
    severity: error            # error | warning
    category: validity
    description: "Order amount must be positive."
    phase: post_transform      # when to evaluate (e.g. pre/post transform)
  # Numeric guardrails without SQL:
  - name: amount_in_range
    sql: "true"
    must_be_between: [0, 100000]
  - { name: min_qty, sql: "true", must_be_greater_than: 0 }
  - { name: max_qty, sql: "true", must_be_less_than: 1000 }
```

| `QualityRule` field | Purpose |
|---|---|
| `name` **(req)** | Rule identifier (shown in quarantine + logs). |
| `sql` **(req)** | Boolean predicate; row passes when true. |
| `severity` | `error` (quarantine/fail) vs `warning` (log only). |
| `category` | Free-form tag (validity, completeness, consistency…). |
| `description` | Human explanation, surfaced on failure. |
| `phase` | When the rule runs relative to transformation. |
| `must_be_between` / `must_be_less_than` / `must_be_greater_than` | Numeric bounds as structured alternatives to SQL. |

### Row-rule shorthands

Common rules have a compact form (each is its own model), so you don't write SQL for the routine ones:

```yaml
row_rules:
  - { not_null: customer_id }
  - { range: { column: amount, min: 0, max: 100000 } }
  - { regex_match: { column: email, pattern: "^[^@]+@[^@]+\\.[^@]+$" } }
  - { accepted_values: { column: status, values: [new, paid, shipped, cancelled] } }
  - { referential_integrity: { column: customer_id, references: "silver_customers.id" } }
  - { lifecycle_window: { column: event_time, window: "30d" } }
```

| Shorthand | Checks |
|---|---|
| `not_null` | Column is never null. |
| `range` | Numeric/temporal value within `[min, max]`. |
| `regex_match` | String matches a pattern. |
| `accepted_values` | Value is in an allow-list (enum). |
| `referential_integrity` | Value exists in a referenced dataset/column (FK). |
| `lifecycle_window` | Timestamp falls within an allowed recency window. |

## Dataset rules

Assertions over the whole dataset (`dataset_rules`) — also available as shorthands:

```yaml
dataset_rules:
  - { unique: order_id }                                   # PK uniqueness
  - { null_ratio: { column: email, max: 0.02 } }          # ≤ 2% nulls
  - { row_count_between: { min: 1000, max: 5000000 } }     # volume sanity
  # or a full QualityRule with aggregate SQL:
  - name: no_future_dates
    sql: "SELECT count(*) = 0 FROM {dataset} WHERE order_date > current_date"
```

| Shorthand | Checks |
|---|---|
| `unique` | No duplicate values in the column(s). |
| `null_ratio` | Null fraction stays under a threshold. |
| `row_count_between` | Row count within `[min, max]`. |

!!! note "Rules that reference injected columns"
    A dataset rule may reference a column that materialization injects later (a surrogate key, SCD2 audit columns). At validation time that column doesn't exist yet and such keys are unique by construction — the runtime treats a "column not found" bind as *not-evaluated-here* (enforced at materialization), not an error.

## Field-level rules

Rules can also travel **with a field** in `model.fields[]`, so validity lives next to the column it constrains:

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

## Quarantine

Failing rows aren't dropped — they're written to a **quarantine** table *with the failed rule and reason*, so nothing is lost and every rejection is auditable (`Quarantine` model).

```yaml
quarantine:
  enabled: true
  table: "orders_quarantine"           # or `location` for a path target
  format: delta                        # delta | iceberg | ducklake | parquet
  write_mode: append
  include_error_reason: true           # attach the failing rule + message per row
  fail_on_quarantine: false            # true → any quarantined row fails the run
  notifications_enabled: true
  strict_notifications: false
  notifications: [ ... ]               # see Notifications
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
