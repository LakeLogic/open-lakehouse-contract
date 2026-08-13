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

A dataset rule is an **aggregate** SQL assertion over the whole good dataset — it returns a scalar (or boolean) that must hold. Where row rules quarantine bad *rows*, dataset rules judge the *whole batch*: they're your **in-pipeline quality gate** for the aggregate invariants that make up a data-quality SLO — volume, completeness, freshness, reconciliation.

**Enforcement — what a failing dataset rule does:**

- `severity: error | warning | info` — `error` fails the rule; `warning` / `info` log only.
- `fail_pipeline_on_dataset_error: true` (on the `quality` block) — a failed error-severity dataset rule **aborts the whole run**, so a bad aggregate never publishes.
- `must_be_between` / `must_be_greater_than` / `must_be_less_than` — bound the scalar the rule's SQL returns (else the SQL should return a boolean).

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

---

## Quality-SLO scenarios

Dataset rules are how you encode data-quality SLOs as **gates** — checked every run, enforced before publish. Each scenario shows the SQL, the rule, and what it protects against. Set `fail_pipeline_on_dataset_error: true` to make these hard gates.

### Volume within band — catch truncated / runaway loads

*A daily feed normally lands 8k–40k rows. A source glitch that ships 200 (or a fan-out bug that ships 400k) should fail, not silently publish.*

```sql
SELECT COUNT(*) BETWEEN 8000 AND 40000 FROM source
```
```yaml
- row_count_between: { min: 8000, max: 40000, category: completeness, severity: error }
```

### Volume drop vs a rolling baseline — silent-stall detection

*Absolute bands miss gradual drift. Compare today's volume to a rolling baseline and fail if it collapses — an upstream feed that quietly stopped.*

```sql
SELECT COUNT(*) * 1.0 / (SELECT avg_daily_rows FROM volume_baseline) FROM source
```
```yaml
links:
  - { name: volume_baseline, table: "reference.gold_volume_baseline", type: table }
quality:
  dataset_rules:
    - name: volume_not_dropped
      sql: "SELECT COUNT(*) * 1.0 / (SELECT avg_daily_rows FROM volume_baseline) FROM source"
      must_be_greater_than: 0.70          # today ≥ 70% of the 30-day average
      severity: error
      category: volume
```

### Completeness threshold — a key column can't go mostly-null

*An upstream schema change nulls `customer_email`. The completeness SLO is "≤ 2% null."*

```sql
SELECT COUNT(*) FILTER (WHERE customer_email IS NULL) * 1.0 / COUNT(*) <= 0.02 FROM source
```
```yaml
- null_ratio: { field: customer_email, max: 0.02, severity: error, category: completeness }
```

### Financial reconciliation — the numbers must tie out

*The classic: net revenue must equal gross − fees − refunds. A reconciliation break (5% off, or 100% off) should stop the run before finance sees wrong totals.*

```sql
SELECT ABS(SUM(net_amount) - SUM(gross_amount - fee_amount - refund_amount)) FROM source
```
```yaml
- name: revenue_reconciles
  sql: "SELECT ABS(SUM(net_amount) - SUM(gross_amount - fee_amount - refund_amount)) FROM source"
  must_be_less_than: 0.01                 # penny tolerance
  severity: error
  category: reconciliation
```

### Freshness gate — block a stale batch

*The batch ran, but every row is a day old — the upstream stalled. Fail the publish. (Complements the freshness [SLO](slo.md), which watches it over time; this blocks the current run.)*

```sql
SELECT max(event_time) >= current_timestamp - INTERVAL 24 HOUR FROM source
```
```yaml
- name: data_is_fresh
  sql: "SELECT max(event_time) >= current_timestamp - INTERVAL 24 HOUR FROM source"
  severity: error
  category: timeliness
```

### Referential completeness — no orphan facts

*Every fact row must match a dimension. Zero facts may reference a driver that isn't in `dim_driver`. This is the dataset-level guarantee behind the row-level `referential_integrity` rule.*

```sql
SELECT COUNT(*) FILTER (WHERE d.driver_id IS NULL)
FROM source f LEFT JOIN dim_driver d ON f.driver_id = d.driver_id
```
```yaml
links:
  - { name: dim_driver, table: "marketplace.gold_rideflow_dim_driver", type: table }
quality:
  dataset_rules:
    - name: no_orphan_facts
      sql: "SELECT COUNT(*) FILTER (WHERE d.driver_id IS NULL) FROM source f LEFT JOIN dim_driver d ON f.driver_id = d.driver_id"
      must_be_less_than: 1
      severity: error
      category: integrity
```

### Distribution / skew guard — catch fan-out & stuck partitions

*No single city should own more than 60% of trips. A runaway join or a stuck partition shows up as skew. Warn (don't block) so the team investigates.*

```sql
SELECT max(city_share) FROM (
  SELECT COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS city_share FROM source GROUP BY city_code
)
```
```yaml
- name: city_distribution_sane
  sql: "SELECT max(city_share) FROM (SELECT COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS city_share FROM source GROUP BY city_code)"
  must_be_less_than: 0.60
  severity: warning
  category: distribution
```

## Dataset rules vs. `service_levels`

Both guard aggregate quality — they differ in **when**:

| | Dataset rules | [`service_levels`](slo.md) (SLOs) |
|---|---|---|
| **When** | In-run, on this batch | Across runs, over time |
| **Effect** | Pass/fail (and can **abort**) the current run before publish | Tracked by the control plane → incidents / notifications |
| **Use for** | *Stop bad data shipping now* | *Track whether the product keeps its promise* |

`row_count` and freshness appear in both by design: the **dataset rule is the hard gate**, the **SLO is the watched target**. Author the gate to protect this run; author the SLO to hold the product accountable over time.

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
