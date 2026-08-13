# Post-Ingestion Lifecycle

Once input has been safely ingested and materialized, what happens to the **source files**? Do they stay, get archived, or get deleted? That's the `post_ingestion` block (`PostIngestionConfig`), available on both `source` and `server`.

!!! abstract "Powered by"
    `PostIngestionConfig` is a **Pydantic** model. File moves/deletes are performed with the same filesystem layer used for reads — local `os`/`shutil`, or **s3fs** / **gcsfs** / **adlfs** (via **fsspec**) for `s3://` / `gs://` / `abfss://`.

## Delete, archive, or retain

```yaml
source:
  type: landing
  path: "s3://bucket/landing/orders/"
  post_ingestion:
    action: delete            # delete | archive | retain
    cleanup_is_blocking: false
    archive_path: "s3://bucket/archive/orders/"   # required when action == archive
```

| Field | Values | Purpose |
|---|---|---|
| `action` | `delete` \| `archive` \| `retain` | What to do with consumed input after a successful run. `retain` (default) leaves it in place; `delete` removes it; `archive` moves it to `archive_path`. |
| `archive_path` | path | Destination for `action: archive`. Required in that mode. |
| `cleanup_is_blocking` | `true` \| `false` | If `true`, the run waits for cleanup to finish (and fails if cleanup fails). If `false`, cleanup is best-effort and non-blocking. |

### When to use each

- **`retain`** — safest; keep the raw input for audit/replay. Pair with a lifecycle policy on the bucket to expire old files.
- **`archive`** — move processed files out of the hot landing path into cold storage, so the landing zone only ever contains un-ingested files (and you keep the originals).
- **`delete`** — reclaim space / enforce data-minimization once the governed copy exists downstream. Use `cleanup_is_blocking: true` when you must *guarantee* the source is gone before the run is considered complete (e.g. a compliance requirement).

!!! warning "Order of operations"
    Cleanup runs **after** a successful materialization. If the write fails, the input is left untouched so the run can be retried. With `action: delete` and `cleanup_is_blocking: false`, a delete failure is logged but does not fail the pipeline — set it to `true` if the delete must be enforced.

## Same control on the `server` block

The `server` block (the target/output connection) also carries `post_ingestion`, so you can express cleanup at the output-binding level as well as the source level:

```yaml
server:
  type: delta
  path: "abfss://lake@acct.dfs.core.windows.net/silver/orders"
  mode: merge
  post_ingestion: { action: archive, archive_path: "abfss://lake@acct.dfs.core.windows.net/_archive/orders" }
```

## Related lifecycle controls

Cleanup is one part of the run lifecycle. The neighbours:

- **Incremental watermark** — [`load_mode: incremental`](ingestion.md#load-modes) persists a watermark so each run only processes new input. Combined with `action: delete`, the landing zone stays small and each file is processed exactly once.
- **Empty input** — `source.empty_behavior: skip | fail` decides whether "no new files" is a no-op or an error.
- **Retry** — `source.retry` (`RetryConfig`: `max_attempts`, `backoff`, `initial_delay`) retries transient read failures before any cleanup happens.
- **Reprocessing** — [`materialization.reprocess_policy`](materialization.md#reprocessing) governs bounded re-runs over a date window without duplicating rows.
