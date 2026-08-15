# Conformance Suite

A contract *conforms* to OLC if it validates against the published JSON Schema. The repo ships a small conformance suite so both authors and alternative frameworks can check themselves against the same corpus.

## Run it

```bash
pip install jsonschema pyyaml
python tests/conformance.py
```

```
  PASS  (expect valid)   examples/orders.olc.yaml
  PASS  (expect valid)   tests/valid/minimal.yaml
  PASS  (expect invalid) tests/invalid/fields_not_a_list.yaml
  PASS  (expect invalid) tests/invalid/info_wrong_type.yaml

OK  - all conformance checks passed
```

## How it's structured

The corpus is split by expected outcome, and the runner enforces both directions — valid fixtures **must pass**, invalid fixtures **must fail**:

```
examples/          illustrative, valid contracts        → must validate
tests/valid/       minimal + edge valid contracts       → must validate
tests/invalid/     deliberately broken contracts        → must NOT validate
```

`tests/conformance.py` recursively loads each YAML, runs it through a `Draft202012Validator` built from `schema/open-lakehouse-contract.schema.json`, and reports the first error for anything that lands on the wrong side. Nested examples such as `examples/external-logic/` are part of the corpus.

## Why both directions matter

A schema that accepts everything is useless. The `tests/invalid/` fixtures pin down what OLC **rejects**, so the spec has teeth:

- `fields_not_a_list.yaml` — `model.fields` must be a list, not a mapping.
- `info_wrong_type.yaml` — `info` must be an object, not a scalar.
- `missing_model.yaml` — every contract must declare its data model.
- `unknown_root_key.yaml` — misspelled or invented top-level vocabulary is rejected.
- `unknown_nested_key.yaml` — misspelled or invented nested vocabulary is rejected.
- `version_not_semver.yaml` — the contract version must use semantic-version form.

Intentional vendor-specific vocabulary remains possible under a namespaced
`extensions` key; `tests/valid/namespaced_extensions.yaml` locks in that escape hatch.

Add a fixture whenever you want to lock in a rule (valid *or* invalid) — it becomes an executable assertion about the spec.

## Executable conformance (behavioural)

Structural fixtures prove a contract *parses*; they say nothing about what a runtime
*does* with it. The **executable-conformance corpus** in [`conformance/`](https://github.com/LakeLogic/open-lakehouse-contract/tree/main/conformance)
closes that gap: each case pairs a contract with input data and the expected
**accepted** rows, **quarantined** rows (with failed-rule attribution), **materialised**
state, and run metadata. The same case runs through multiple engine adapters (today
**DuckDB** and **Polars**) and every one must reproduce the same *normalised* outcome —
turning "one contract, any engine" into a repeatable guarantee instead of a claim.

| Level | Proves |
|---|---|
| `document` | Contract validates against the JSON Schema (the fixtures above). |
| `core-runtime` | Schema, quality and quarantine semantics. |
| `materialization` | append / overwrite / merge / SCD2 state. |
| `operational` | lineage, SLOs, run metadata, failure semantics. |
| `provider` | a real platform adapter passes the applicable suite. |

Run it (needs the LakeLogic runtime + `polars`, `duckdb`, `deltalake`):

```bash
python -m pytest conformance -q
```

In CI the same suite runs against a **pinned** LakeLogic revision with
`OLC_CONFORMANCE_REQUIRE=1`, which turns any skipped dependency or unsupported *core*
feature into a hard failure — so a broken engine implementation cannot merge green.
Unsupported *optional* features are reported in a separate capability matrix, never
counted as success. The corpus already earned its keep: it caught and drove the fix
for a real cross-engine execution-order defect in the Polars runtime. See
[`conformance/README.md`](https://github.com/LakeLogic/open-lakehouse-contract/tree/main/conformance).

## For alternative frameworks

Because the spec is a language-neutral JSON Schema, a framework written in any language can validate OLC files without Python. The corpus is the shared reference: point your own validator at `schema/` and the `tests/` fixtures to prove your implementation agrees with the spec, and mirror the language-neutral `conformance/cases/` (JSON Lines input + expected output) to prove your *runtime* agrees behaviourally.
