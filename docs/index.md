---
title: Open Lakehouse Contract
description: One executable contract for a data product — ingest from any source, govern it, land it in an open lakehouse, publish it anywhere. Portable, SQL-native, engine-agnostic; executed unchanged by any conforming framework.
---

<div class="ll-eyebrow"><span class="ll-eyebrow__pip"></span> Apache 2.0 · reference lightweight framework: LakeLogic</div>

<div class="hero-section"><div class="hero-content"><h1 class="hero-title">One contract.<br><span style="color:var(--md-accent-fg-color)">Every lakehouse.</span></h1><p class="hero-subtitle">One executable contract for a data product — pull data from any source, govern it, land it in an open lakehouse, and publish it anywhere. It's just YAML, and the same file runs unchanged on Spark, DuckDB, or Polars — writing Delta, Iceberg, or DuckLake.</p><div class="hero-cta"><a class="md-button md-button--primary" href="getting-started.html">Get started →</a> <a class="md-button md-button--secondary" href="providers/index.html">See the providers</a> <a class="md-button" href="https://github.com/LakeLogic/open-lakehouse-contract" target="_blank">★ Star on GitHub</a></div></div><div class="hero-visual"><div class="ll-win ll-win--yaml"><div class="ll-win__head"><span class="ll-win__dots"><i></i><i></i><i></i></span><span class="ll-win__name">orders.olc.yaml</span></div><pre class="ll-code"><span class="k">version</span>: <span class="n">1.0.0</span>
<span class="k">info</span>: { <span class="k">title</span>: Orders, <span class="k">table_name</span>: orders }

<span class="k">model</span>:
  <span class="k">fields</span>:
    - <span class="k">name</span>: order_id
      <span class="k">type</span>: <span class="s">integer</span>
      <span class="k">required</span>: <span class="b">true</span>
<span class="hl">    - <span class="k">name</span>: customer_email
      <span class="k">type</span>: <span class="s">string</span>
      <span class="k">pii</span>: <span class="b">true</span>
      <span class="k">masking</span>: <span class="s">partial</span></span>
<span class="k">quality</span>:
  <span class="k">row_rules</span>:
    - <span class="k">sql</span>: <span class="s">"amount &gt; 0"</span>
<span class="k">materialization</span>: { <span class="k">strategy</span>: <span class="s">merge</span>, <span class="k">format</span>: <span class="s">iceberg</span> }</pre></div><div class="ll-pr"><div class="ll-pr__head"><span class="ll-pr__num">pull request #128</span><span class="ll-pr__count">2 of 3 passed</span></div><div class="ll-pr__check"><span class="ll-ck ll-ck--ok">✓</span><span class="ll-pr__name">ci / <b>build</b></span><span class="ll-res ll-res--ok">Passed</span></div><div class="ll-pr__check"><span class="ll-ck ll-ck--ok">✓</span><span class="ll-pr__name">ci / <b>unit-tests</b></span><span class="ll-res ll-res--ok">Passed</span></div><div class="ll-pr__check"><span class="ll-ck ll-ck--no">✕</span><span class="ll-pr__name">olc / <b>data-contract</b></span><span class="ll-res ll-res--no">Breaking</span></div></div></div></div>

An Open Lakehouse Contract (OLC) is a single YAML file that declares a dataset's **schema, quality rules, PII handling, lineage, materialization, and SLOs**. Unlike a purely *descriptive* data-contract spec, an OLC is **executable**: a conforming framework validates, quarantines, enforces, masks, and materializes the declared intent straight from the file — so the standard and the implementation can't drift. The contract itself doesn't run anything; it's the portable *intent*, and any conforming framework carries it out.

That same contract runs on **Spark / DuckDB / Polars**, materializes to **Delta / Iceberg / DuckLake**, on **Databricks / Snowflake / Fabric / BigQuery / AWS / MotherDuck** — [see it proven on each →](providers/index.md).

!!! tip "SQL-native"
    Transformation logic is **SQL** — the universal data language — not Python, not Spark code, not notebooks. Write SQL in the contract; the framework runs it, unchanged, on whichever engine you point it at. The shorthand ops (`rename`, `filter`, `join`, `rollup`, …) are convenience wrappers that **compile to SQL** — each shows its SQL variant in the [Transformation reference](reference/transformation.md).

---

## Terraform for the lakehouse

Terraform's real power isn't HCL — it's the **separation of a declarative spec from pluggable providers that execute it**: one language, many backends, each documented against the same vocabulary. OLC has the same shape, applied to data products instead of infrastructure:

| Terraform | Open Lakehouse Contract |
|---|---|
| HCL + resource schema | The OLC contract (JSON Schema, derived from Pydantic) |
| Providers (aws, azurerm, google…) | Frameworks: engines × table formats × platforms |
| `terraform apply` → converge to desired state | `materialize` (merge / SCD2) → converge a table to declared shape + quality |
| Registry + per-provider docs | [The provider matrix](providers/index.md) |

And OLC is *simpler* than Terraform in one important way: Terraform has hundreds of resource types to learn, one per provider. OLC has **one universal resource — the data contract — that every backend implements**. The "registry" is one canonical contract rendered across a matrix of backends.

!!! note "Precise framing"
    OLC is *to data products what Terraform is to infrastructure* — declarative, portable, backend-pluggable. It governs the **data plane** (the data itself), not the control plane (infra). It converges one data product per run; cross-contract drift/state tracking lives in the [LakeLogic](https://lakelogic.org) framework, not the open spec.

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

*The spec is the JSON Schema; [LakeLogic](https://lakelogic.org) is the canonical reference framework that implements it. This project is intentionally vendor-neutral.*
