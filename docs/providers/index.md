# Providers

**One executable contract model for every lakehouse — powered by LakeLogic and proven live across Databricks, Snowflake, BigQuery, AWS, DuckLake, and MotherDuck** (with Microsoft Fabric validated and deploy-ready).

This is the OLC equivalent of the Terraform Registry: **one canonical contract, rendered across a matrix of backends.** The RideFlow data mesh — the *same* contract model throughout — has been run on each platform below; only the backend-owned execution settings (engine, format, catalog, storage) change. Every provider page shows the identical contract, the framework invocation for that backend, and what it materialized.

!!! info "What's RideFlow?"
    **RideFlow** is the running example used throughout OLC: a realistic, **fictional ride-hailing company (like Uber)** — its data mesh spans **6 domains** (marketplace, payments, operations, marketing, reference, shared) across **11 source systems** (Stripe, Twilio, Zendesk, Checkr, Google Ads, HubSpot, and more), ~60 governed tables through a bronze → silver → gold medallion. It exists as one set of OLC contracts; each provider page runs *those exact contracts* on a different lakehouse. Think of it as the "hello world" that's big enough to be real — nothing here is platform-specific to any one backend.

The contract never changes between these pages. Only the `engine`, the `format`, and where the data lands do.

## The matrix

| Platform | Engine(s) | Format | Scope & status | Reference repo |
|---|---|---|---|---|
| **[DuckDB / DuckLake](duckdb-ducklake.md)** | DuckDB | DuckLake | ✅ Live — full 6-domain mesh, ~59 tables | *Coming soon* |
| **[MotherDuck](motherduck.md)** | DuckDB | DuckLake | ✅ Live — marketplace domain, 18 tables + snapshots | *Coming soon* |
| **[Databricks](databricks.md)** | Spark, Polars, DuckDB | Delta | ✅ Live — full mesh on UC; external ADLS Delta via Polars/DuckDB | [GitHub ↗](https://github.com/LakeLogic/lakelogic-databricks-data-mesh-lakehouse) |
| **[Snowflake](snowflake.md)** | Snowflake SQL | Native tables | ✅ Live — full mesh on a trial, + native Project | [GitHub ↗](https://github.com/LakeLogic/lakelogic-snowflake-data-mesh-lakehouse) |
| **[BigQuery (GCP)](bigquery.md)** | BigQuery, Spark | BigQuery native, Iceberg | ✅ Live — 11/11 systems; 18 Iceberg tables | *Coming soon* |
| **[AWS (Glue)](aws.md)** | Spark | Iceberg | ✅ Live — reference + marketplace; one Silver job on Spark 3.5 | *Coming soon* |
| **[Microsoft Fabric](fabric.md)** | Spark | Delta | ◑ Validated & deploy-ready — assign a capacity | [GitHub ↗](https://github.com/LakeLogic/lakelogic-microsoft-fabric-data-mesh-lakehouse) |

!!! note "How to read 'scope & status'"
    ✅ **Live** = the contracts were executed on that platform and materialized real tables (scope stated per row). ◑ **Static preview** (Fabric) = validated and deploy-ready; Fabric is capacity-based, so a live run expects an **F-SKU (or trial) capacity assigned to the workspace** — a normal customer prerequisite. Each provider page states exactly what ran — no silent gaps.

    *Each **reference repo** is the reproducibility artifact for that backend — the exact contracts, the framework invocation, and the run output. They are made public alongside the OLC release.*

## What "same contract" means here

Each provider page starts from a shared RideFlow silver contract like this:

```yaml
version: 1.0.0
info: { title: Trips, table_name: silver_rideflow_trips, target_layer: silver }
model:
  fields:
    - { name: trip_id,   type: string, required: true }
    - { name: rider_id,  type: string, required: true }
    - { name: fare_amount, type: float }
    - { name: rider_email, type: string, pii: true, masking: partial }
primary_key: [trip_id]
quality:
  row_rules:
    - { name: fare_non_negative, sql: "fare_amount >= 0" }
materialization: { strategy: merge }     # format chosen per-platform
```

The only per-platform choices are the ones a backend legitimately owns:

```mermaid
flowchart LR
    K[One RideFlow contract set] --> D["DuckDB · DuckLake · local/S3/GCS/ADLS<br/>(DuckDB / DuckLake)"]
    K --> MD["DuckDB · DuckLake · MotherDuck<br/>(MotherDuck)"]
    K --> DB["Spark · Delta · Unity Catalog<br/>(Databricks)"]
    K --> SF["Snowflake · native · Task DAG<br/>(Snowflake)"]
    K --> BQ["BigQuery · native + Iceberg · GCS<br/>(BigQuery / GCP)"]
    K --> FB["Spark · Delta · OneLake<br/>(Microsoft Fabric)"]
    K --> AW["Spark · Iceberg · Glue + S3<br/>(AWS Glue)"]
```

## Special configurations

Like Terraform's per-provider "special configuration" notes, each backend has a small number of real quirks the framework handles for you. The short version:

| Platform | Notable per-backend handling |
|---|---|
| Snowflake | UPPERCASE identifier casing + dedup ordering; `TO_VARCHAR` casts; native Project from repo root |
| BigQuery | Backtick-quoted identifiers; client location; `TEMP` needs a session; `CONCAT_WS` / `TO_DATE` rewrites |
| DuckLake | `ATTACH 'ducklake:…' (DATA_PATH …)` locally; `CREATE DATABASE … (TYPE DUCKLAKE)` on MotherDuck |
| AWS Glue | Glue Catalog-registered Iceberg; checkpoint-before-merge to avoid Catalyst plan explosion |
| Azure/Fabric | OneLake schema-enabled Lakehouse; REST/OneLake deploy via `az` token |

Each is covered on the platform's page.
