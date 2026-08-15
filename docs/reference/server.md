---
title: Server & Output
description: The `server` block — the target/output warehouse connection context, covering where and how a run writes, the validate/ingest mode, schema-drift policy, and post-ingestion cleanup.
---

# Server & output (`server`)

Where `source` describes *where the data comes from*, the **`server`** block describes the **target/output connection context** — the warehouse or object store a run binds to, and *how* the run behaves against it (most importantly, whether it runs as a **Quality Gate** (`validate`) or performs **Raw-to-Bronze** movement (`ingest`)).

```yaml
server:
  type: warehouse            # the target server / warehouse kind
  format: parquet            # output format (default: parquet)
  path: "s3://lake/orders"   # target location (path / URI)
  mode: validate             # validate — Quality Gate (default) | ingest — Raw-to-Bronze movement
  cast_to_string: false      # read every column as string (bronze pattern) — bad types quarantine downstream
  schema_policy:             # how schema drift is handled at the target
    evolution: allow
    unknown_fields: allow
  post_ingestion:            # what happens to the consumed input after a run
    action: retain
    archive_path: "s3://lake/_archive/orders"
    cleanup_is_blocking: false
```

## Fields

| Field | Type | Default | What it does |
|---|---|---|---|
| `type` | string | — | The target server / warehouse kind this run binds to. |
| `format` | string | `parquet` | Output format written at the server. |
| `path` | string | — | **Required.** Target location (path / URI). |
| `mode` | string | `validate` | **`validate`** — Quality-Gate mode (run schema + quality checks); **`ingest`** — Raw-to-Bronze movement (move raw input into bronze). Default `validate`. |
| `cast_to_string` | boolean | `false` | Read every column as string (the bronze pattern), so malformed values quarantine downstream instead of failing the read. |
| `schema_policy` | object | — | How schema drift is absorbed at the target — same shape as [schema policy](lifecycle.md) elsewhere. |
| `post_ingestion` | object | — | What happens to the consumed input *after* a successful run. See [Post-Ingestion Lifecycle](lifecycle.md#same-control-on-the-server-block). |

### `schema_policy` — how schema drift is absorbed

**`evolution`** — what to do when the incoming schema differs from the contract (default `allow`):

| Value | What it does | Use it when |
|---|---|---|
| `strict` | Reject **any** schema change — the incoming schema must match the contract exactly, or the run fails. | Locked / regulated tables where drift must be a hard error. |
| `compatible` | Allow only **backward-compatible** changes (add nullable columns, widen types); reject breaking ones. | Evolving contracts with live consumers — the safe non-trivial setting. |
| `append` | **Add** new columns; leave existing columns untouched. | Additive sources that gain optional fields over time. |
| `merge` | Add new columns **and** reconcile compatible type changes. | Schemas that both gain columns and shift types. |
| `overwrite` | Replace the target schema with the incoming one. | Full-refresh tables where the source is authoritative. |
| `allow` *(default)* | Accept any change — most permissive. | Bronze / landing, where you take whatever arrives and resolve it downstream. |

**`unknown_fields`** — what to do with columns present in the data but **not declared** in the contract (default `allow`):

| Value | What it does | Use it when |
|---|---|---|
| `quarantine` | Route rows carrying undeclared columns to [quarantine](quality.md#quarantine), kept with the reason. | Catch unexpected columns without silently losing data. |
| `drop` | Silently drop undeclared columns — project the output to the contract's shape. | Enforce a clean, exact output schema. |
| `allow` *(default)* | Keep undeclared columns as-is (passthrough). | Bronze / flexible ingestion where extra columns are fine. |

### `post_ingestion` — what happens to the consumed input

Cleanup of the input files, expressible at both the [`source`](ingestion.md) and the `server` level.

**`action`** (default `retain`):

| Value | What it does | Use it when |
|---|---|---|
| `retain` *(default)* | Leave the input in place. | Reprocessing, audit, idempotent re-runs. |
| `delete` | Delete the input after a successful run. | Data minimization / reclaiming space. Pair with `cleanup_is_blocking: true` to **guarantee** it's gone before the run reports success (e.g. a compliance requirement). |
| `archive` | Move the input to `archive_path`. | Keep a cold copy for audit while clearing the landing zone. |

| Field | Type | Default | |
|---|---|---|---|
| `archive_path` | string | — | Where input lands when `action: archive`. |
| `cleanup_is_blocking` | boolean | `false` | Whether cleanup must finish before the run is considered complete. |

The write side (`strategy`, `format`, `location`) is in [Materialization & Storage](materialization.md); the same delete / archive / retain behaviour is covered in depth in [Post-Ingestion Lifecycle](lifecycle.md).
