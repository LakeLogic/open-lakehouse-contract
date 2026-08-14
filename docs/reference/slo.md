# Service Levels (SLOs)

A data product isn't done when it materializes — it has to *stay* fresh and complete. OLC declares **service-level objectives** (`service_levels`) as a first-class part of the contract: the freshness, availability, and volume targets the data must keep meeting.

!!! abstract "Powered by"
    `ServiceLevel` is a **Pydantic** model. SLO checks run as engine queries (**PySpark** / **duckdb** / **polars**) after materialization; breaches raise [notifications](notifications.md) and feed the control plane's incidents/dashboards.

## Shape

```yaml
service_levels:
  freshness:
    threshold: "6h"           # data must be no older than 6 hours
    field: updated_at         # the column freshness is measured on
    description: "Orders land within 6h of the source event."
  availability: 0.999         # 99.9% of runs succeed
  row_count:
    min_rows: 1000
    max_rows: 5000000
    check_field: order_date
    skip_reprocess_days: 2
    description: "Daily volume sanity."
```

## `freshness` — `string | ServiceLevelObjective`

How recent the data must be. Shorthand as a duration string (`"6h"`), or the full form:

| `ServiceLevelObjective` | Purpose |
|---|---|
| `threshold` | The bound (a duration like `6h`, or a number). |
| `field` | The column measured against `now()`. |
| `description` | Human explanation, surfaced on breach. |

## `availability` — `number | ServiceLevelObjective`

The success-rate target (e.g. `0.999`), or a full objective with a description.

## `row_count` — `RowCountSLO`

Volume expectations, with reprocess-awareness:

| Field | Purpose |
|---|---|
| `min_rows` / `max_rows` | Acceptable row-count band. |
| `check_field` | Column scoping the count (e.g. per-day). |
| `skip_reprocess_days` | Don't alarm on recent days still being backfilled. |
| `description` | Human explanation. |

SLO breaches integrate with the control plane (incidents, dashboards) — the contract is where the target is *declared*; the framework and platform are where it's *watched*. A downstream consumer's expectation of this product is captured on the [lineage graph](lineage.md#2-contract-level-lineage-graph) (`downstream[].sla`).

## Related

- [Lineage](lineage.md) — provenance, the contract graph, and the pipeline DAG (moved to its own page).
- [Notifications](notifications.md) — how an SLO breach raises an alert.
