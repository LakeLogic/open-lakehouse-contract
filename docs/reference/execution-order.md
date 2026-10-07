# Execution Order (pre & post)

Several parts of a contract carry a `phase: pre | post` — most visibly [transformations](transformation.md#phase-pre-or-post) and [quality rules](quality.md). "Pre" and "post" only mean something against the **run sequence**, so this page captures the whole order in one place: what runs, when, and which columns each phase can see.

## The canonical sequence

A single run executes these steps in order:

```mermaid
flowchart TD
    S[1 · Source] --> PRE[2 · Pre-transforms] --> SE[3 · Schema] --> PQ[4 · Pre-quality] --> SPLIT{5 · Good / bad}
    SPLIT -->|good rows| POST[6 · Post-transforms] --> POQ[7 · Post-quality] --> M[8 · Materialize] --> C[9 · Cleanup]
    SPLIT -->|bad rows| Q[(Quarantine)]
```

| Step | Stage | What happens |
|---|---|---|
| 1 | **Source loaded** | Raw data read from the source (file / table / API / stream). See [Ingestion](ingestion.md). |
| 2 | **Pre-transforms** | `phase: pre` transforms — shape raw input before it's checked. |
| 3 | **Schema enforcement** | Columns cast to the contract's declared types. |
| 4 | **Pre quality rules** | `phase: pre` rules validate **source** columns. |
| 5 | **Good / bad split** | Failing rows are routed to [quarantine](quality.md#quarantine) with the rule + reason; good rows continue. |
| 6 | **Post-transforms** | `phase: post` transforms — enrich validated data (joins, derived fields, rollups). |
| 7 | **Post quality rules** | `phase: post` rules validate **derived** columns. |
| 8 | **Materialize** | Converge the target table per [materialization](materialization.md). |
| 9 | **Post-ingestion cleanup** | Delete / archive / retain the consumed input — see [Lifecycle](lifecycle.md). |

## Pre vs post — the rule of thumb

The split at step 5 (good/bad) is the dividing line, and it determines what each phase can reference:

| | **Pre** | **Post** |
|---|---|---|
| Runs | Before quality checks (steps 2 & 4) | After the good/bad split (steps 6 & 7) |
| Can reference | **Source columns only** | Source **and** derived columns |
| Typical use | Clean/normalize raw input so it *passes* validation — rename, cast, trim, filter, deduplicate | Enrich validated data — derive, lookup, join, rollup, pivot, SQL |
| Operates on | The full raw dataset | Only the rows that passed validation |

!!! tip "Why the order matters"
    - **Put normalization in `pre`** so a rule like `email IS NOT NULL` checks *cleaned* values, not raw ones — otherwise you quarantine rows that a `trim`/`coalesce` would have rescued.
    - **Put enrichment in `post`** so joins/derivations run only on good rows (cheaper, and you never enrich a row that's about to be quarantined).
    - A field derived in a `post` transform can be validated by a `post` quality rule — but **not** a `pre` rule, because it doesn't exist yet at step 4.

## Declaring the phase

```yaml
transformations:
  - trim: { fields: [email], side: both }         # normalize BEFORE checks
    phase: pre
  - derive: { field: line_total, sql: "qty * price" }   # enrich AFTER the split
    phase: post

quality:
  row_rules:
    - { name: email_present, sql: "email IS NOT NULL", phase: pre }   # checks source
    - { name: total_positive, sql: "line_total > 0",   phase: post }  # checks derived
```

If you omit `phase` on a **transformation**, it runs in `post` — every kind, normalizing ones included. Write `phase: pre` on a `trim`, `cast` or `rename` that checks depend on.

## When a check's phase is not written

A quality check whose `phase` you leave out runs **where its columns exist**:

- in the **pre** phase, unless
- it reads a column that only a **post** transformation creates (a `derive`, `json_extract`, `lookup`, `join`, `rollup`, SQL alias, …) — then in the **post** phase.

This covers `required: true` and other field-level checks on model fields, and row rules without a `phase`. A gold model describes its **output**, so `required: true` on a column the post SQL builds means "required in the output":

```yaml
model:
  fields:
    - { name: created_date, type: date, required: true }   # built below: checked after the SQL
transformations:
  - sql: SELECT CAST(created_at AS DATE) AS created_date, ... FROM source GROUP BY 1
```

A check **written** `phase: pre` always runs pre. If it reads a column only a post transformation creates, that column does not exist yet, so every row would fail: `lakelogic lint` reports it as **PHS-001**.

A transformation that **rewrites** a column in place (`trim`, `cast`, `derive` of an existing field) does not create it: a pre check of that column checks the **source** value.

Every runtime follows this order. Conformance cases `OLC-EO-001`–`OLC-EO-005` check it on each engine.

## Related

- [Transformation](transformation.md) — the ops available in each phase (SQL variant + shorthand).
- [Validation & Quality](quality.md) — row/dataset rules and how the good/bad split feeds quarantine.
- [Post-Ingestion Lifecycle](lifecycle.md) — what happens to the source after step 8.
