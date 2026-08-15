# OLC Executable Conformance

Proving *observable runtime behaviour* — not merely that YAML parses. A conforming
runtime, given a contract + input, must produce the right **accepted** rows,
**quarantined** rows (with failed-rule attribution), **materialised** state, and
**run metadata**. The same case runs against multiple engines through adapters; if
they produce the same *normalised* outcome, the "one contract across engines" claim
becomes a repeatable guarantee instead of prose.

## Levels

| Level | Proves |
|---|---|
| `document` | Contract validates against the JSON Schema (see `../schema` + drift gate) |
| `core-runtime` | Schema, quality and quarantine semantics |
| `materialization` | append / overwrite / merge / SCD2 state |
| `operational` | lineage, SLOs, run metadata, failure semantics |
| `provider` | a real platform adapter passes the applicable suite |

## Layout

```
conformance/
├── specification.yaml     # spec version, levels, comparison defaults, outcomes
├── cases/<case>/          # one language-neutral behavioural case each
│   ├── case.yaml          # id, level, feature, assertions, comparison
│   ├── contract.olc.yaml
│   ├── input.jsonl
│   ├── seed.jsonl         # prior target state (materialisation cases)
│   └── expected/          # accepted.jsonl / quarantined.jsonl / target.jsonl
├── runner/                # ExecutionResult, adapter protocol, normaliser, harness
└── test_conformance.py    # runs every case × every core adapter
```

## Running

```bash
pip install lakelogic polars deltalake pyyaml pytest
python -m pytest conformance/test_conformance.py -q
```

Each case is authored once and must reproduce identically on every core adapter
(currently **DuckDB** and **Polars**). Comparison is on *semantic outcome*: row and
column order are ignored, numbers are compared to a tolerance, and volatile fields
(run IDs, timestamps) are stripped.

## Outcomes

`PASS` (declared feature behaved correctly) · `FAIL` (declared feature misbehaved) ·
`UNSUPPORTED` (feature not declared by the adapter — never silently a PASS) · `SKIP`.

## Known gaps

None currently. The `KNOWN_GAPS` registry in `test_conformance.py` is the mechanism
for tracking any future cross-engine defect as a strict xfail (which flips to a
failure the moment the engine is fixed, prompting removal).

**First find (fixed).** On its first run the corpus caught a real cross-engine
defect: the **Polars engine evaluated a pre-phase quality rule before the pre-phase
transform**, so a derived column was missing (`ColumnNotFoundError`) — a violation of
the documented `transform → quality` order that DuckDB got right. Root cause: the
post-transform pass re-ran pre-phase `derive` steps (its `derive` handler lacked the
`phase != "pre"` guard its sibling handlers have) and dropped the derived column.
Fixed in `engines/polars.py`. This is the harness doing its job — catching semantic
drift between adapters that a schema check never could.

## Adding a case

1. `mkdir cases/<name>` with `case.yaml`, `contract.olc.yaml`, `input.jsonl`, `expected/`.
2. Give it a stable ID (`OLC-Q-###`, `OLC-MERGE-###`, …) and set `level` + `feature`.
3. Author `expected/*.jsonl` from the *correct* semantics (verify, don't just capture
   one engine's output), then confirm all core adapters agree.
