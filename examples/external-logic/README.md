# Example — external logic (a PySpark job under an OLC contract)

A `silver_trips` data product whose transformation is a **reusable PySpark job**, still
fully governed by the contract. Shows how complex compute plugs into OLC via
[`external_logic`](../../docs/reference/external-logic.md).

## Files
- [`silver_trips.olc.yaml`](silver_trips.olc.yaml) — the contract: schema, quality, PII,
  lineage, materialization, SLO — plus an `external_logic` block pointing at the job.
- [`sessionize_trips.py`](sessionize_trips.py) — the PySpark job. Entry point
  `run(df, contract=, engine=, **args)` adds a `session_id` and returns the frame.

## The split
- **The contract owns governance**: `trip_id` unique, `fare_amount >= 0`, `rider_email`
  is PII (masked), freshness ≤ 6h, materialize as `merge`.
- **The job owns the compute**: per-rider sessionization with a Spark window.
- `handles_output: false` → the job returns a dataframe; **OLC materializes it and
  enforces the contract**. (Set `true` if the job writes the table itself and OLC should
  just validate the result.)

## Validate it (no runtime needed)
```bash
pip install jsonschema pyyaml
olc validate silver_trips.olc.yaml          # or: python ../../scripts/validate.py silver_trips.olc.yaml
```

## Run it (needs the reference runtime + Spark)
```bash
pip install lakelogic
# generate synthetic trips FROM the contract, then run the governed pipeline (incl. the job)
lakelogic generate --contract silver_trips.olc.yaml --rows 2000 --output trips.parquet
# ... feed trips.parquet through the processor with engine=spark ...
```

## When to reach for this
`external_logic` is the escape hatch, **not** the default. Sessionization here *could* be
a windowed SQL `transformations` step kept entirely in-contract — it's shown as external
logic only to illustrate reusing an existing Spark job. Choose based on complexity: stay
in OLC's SQL-first transformations where you can; reference external code when the logic
genuinely exceeds SQL or you're reusing existing code. See
[Rewrite in OLC, or reference it?](../../docs/reference/external-logic.md#rewrite-in-olc-or-reference-it).
