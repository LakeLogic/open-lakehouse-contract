# OLC-S-001 — `source.flatten_nested` at read time

## What this case pins

A bronze table stores a nested object as a **JSON string**. The contract declares
the flat `payload_a` / `payload_b` columns and sets `source.flatten_nested: true`.
The case pins that the JSON string is expanded into those columns during the
source read, so validation sees the schema the contract declares.

## Why it needs `input_via: source`

Flattening happens on the **read path**. Every other case in this corpus hands
`DataProcessor.run()` an already-loaded frame, which skips that path entirely — so
before this case existed, `flatten_nested` was unreachable by construction and
could not have been tested no matter what the contract said.

`input_via: source` writes the input to a real parquet file and calls
`run_source()` instead. See `ConformanceCase.input_via`.

## Why every column is a string

Deliberate isolation, not laziness. Writing the parquet with an `integer` id
produced INT64, while the runtime applies the contract schema to the Spark reader
as INT32, and Spark's vectorised parquet reader refuses the widening
(`PARQUET_COLUMN_DATA_TYPE_MISMATCH`). That is a real question about physical type
strictness on the read path, but it is **not** what this case is about, and
letting it fail here would have blamed `flatten_nested` for something else. It is
worth its own case.

## Current engine behaviour

| Engine | Behaviour | Verdict |
| --- | --- | --- |
| DuckDB | flattens | conforms |
| Polars | flattens | conforms |
| Spark | columns are NULL, rows **accepted** | silent data loss |

Spark's failure is the dangerous kind: nothing raises, nothing warns, and the run
reports success while the declared columns are empty. Recorded in `KNOWN_GAPS`.
