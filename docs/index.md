# Open Lakehouse Contract

**One human-readable contract that both *describes* and *executes* a data product — portable across engines, table formats, and platforms.**

An Open Lakehouse Contract (OLC) is a single YAML file that declares a dataset's **schema, quality rules, PII handling, lineage, materialization, and SLOs**. Unlike a purely *descriptive* data-contract spec, an OLC is **executable**: a conforming runtime validates, quarantines, enforces, masks, and materializes straight from the file — so the standard and the implementation can't drift.

```yaml
version: 1.0.0
info: { title: Orders, table_name: orders, target_layer: silver }
model:
  fields:
    - { name: order_id, type: integer, required: true }
    - { name: customer_email, type: string, pii: true, masking: partial }
    - { name: amount, type: float, required: true }
primary_key: [order_id]
quality:
  row_rules:
    - { name: positive_amount, sql: "amount > 0" }
materialization: { strategy: merge, format: iceberg }
```

That same file runs on **Spark / DuckDB / Polars**, materializes to **Delta / Iceberg / DuckLake**, on **Databricks / Snowflake / Fabric / BigQuery / AWS / MotherDuck** — [see it proven on each →](providers/index.md).

---

## Terraform for the lakehouse

Terraform's real power isn't HCL — it's the **separation of a declarative spec from pluggable providers that execute it**: one language, many backends, each documented against the same vocabulary. OLC has the same shape, applied to data products instead of infrastructure:

| Terraform | Open Lakehouse Contract |
|---|---|
| HCL + resource schema | The OLC contract (JSON Schema, derived from Pydantic) |
| Providers (aws, azurerm, google…) | Runtimes: engines × table formats × platforms |
| `terraform apply` → converge to desired state | `materialize` (merge / SCD2) → converge a table to declared shape + quality |
| Registry + per-provider docs | [The provider matrix](providers/index.md) |

And OLC is *simpler* than Terraform in one important way: Terraform providers expose hundreds of distinct resource types, so their docs sprawl. OLC has **one universal resource — the data contract — that every backend implements**. The "registry" is one canonical contract rendered across a matrix of backends.

!!! note "Precise framing"
    OLC is *to data products what Terraform is to infrastructure* — declarative, portable, backend-pluggable. It governs the **data plane** (the data itself), not the control plane (infra). It converges one data product per run; cross-contract drift/state tracking lives in the [LakeLogic](https://lakelogic.org) runtime, not the open spec.

---

## Why OLC

- **Executable, not just descriptive.** The same file that documents the contract *runs* it — validation, quarantine, quality gates, PII masking, lineage, materialization. No spec-vs-implementation gap.
- **Portable.** One contract, every lakehouse. The backend is a flag; the contract is the invariant.
- **Broader than "data contract."** OLC covers the whole lakehouse surface — schema **+ quality + PII + lineage + materialization + SLOs** — not just schema.
- **Agent-native.** Typed, self-validating, and executable — the ideal substrate for [AI data agents](concepts/agent-native.md): they can *generate* it (schema-constrained), *self-correct* against validation errors, *act* and observe real outcomes, and reason about the same contract on every platform.

---

## Where to go next

<div class="grid cards" markdown>

- :material-rocket-launch: **[Getting Started](getting-started.md)** — validate a contract in 60 seconds.
- :material-file-document: **[What is OLC?](concepts/what-is-olc.md)** — the executable-contract idea in full.
- :material-view-grid: **[Providers](providers/index.md)** — the same contract, proven on 7 platforms.
- :material-code-json: **[Field Reference](reference/schema.md)** — every field in the spec.

</div>

---

*The spec is the JSON Schema; [LakeLogic](https://lakelogic.org) is the canonical reference runtime that implements it. This project is intentionally vendor-neutral.*
