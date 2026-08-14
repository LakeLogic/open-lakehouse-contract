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

`tests/conformance.py` loads each YAML, runs it through a `Draft202012Validator` built from `schema/open-lakehouse-contract.schema.json`, and reports the first error for anything that lands on the wrong side.

## Why both directions matter

A schema that accepts everything is useless. The `tests/invalid/` fixtures pin down what OLC **rejects**, so the spec has teeth:

- `fields_not_a_list.yaml` — `model.fields` must be a list, not a mapping.
- `info_wrong_type.yaml` — `info` must be an object, not a scalar.

Add a fixture whenever you want to lock in a rule (valid *or* invalid) — it becomes an executable assertion about the spec.

## For alternative frameworks

Because the spec is a language-neutral JSON Schema, a framework written in any language can validate OLC files without Python. The conformance corpus is the shared reference: point your own validator at `schema/` and the `tests/` fixtures to prove your implementation agrees with the spec. A language-neutral test corpus (beyond the Python runner) is [on the roadmap](../contributing.md).
