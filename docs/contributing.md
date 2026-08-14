# Contributing

The Open Lakehouse Contract is intentionally vendor-neutral. Contributions are welcome — especially conformance fixtures, alternative-language validators, and provider write-ups from real runs.

## Repo layout

```
schema/     the spec — open-lakehouse-contract.schema.json (generated, do not hand-edit)
scripts/    generate_schema.py — regenerates the schema from the reference framework
examples/   illustrative valid contracts
tests/      conformance suite: valid/ (must pass), invalid/ (must fail) + conformance.py
docs/       this site (mkdocs-material)
```

## The schema is generated, never hand-edited

The JSON Schema is derived from the reference framework's Pydantic models. **Don't edit `schema/` by hand** — change the reference model and regenerate:

```bash
pip install lakelogic
python scripts/generate_schema.py
```

This keeps the spec provably in sync with a working implementation (see [Why Pydantic](concepts/why-pydantic.md)). A PR that edits the schema directly will drift from the framework and be rejected.

## Adding a conformance fixture

The highest-leverage contribution is a fixture that pins down a rule:

1. Add a `.yaml` under `tests/valid/` (must validate) or `tests/invalid/` (must fail).
2. Run `python tests/conformance.py` — it must stay green.
3. Note in your PR what rule the fixture locks in.

## Build the docs locally

```bash
pip install mkdocs-material
mkdocs serve            # http://127.0.0.1:8011
```

## Roadmap

- **Language-neutral test corpus** — conformance fixtures consumable by validators in any language, not just the Python runner.
- **Formal versioning & governance** — a documented process for evolving the spec across `v1` → `v2`.
- **More provider write-ups** — each backed by an actual run, with honest status labels (✅ Live / ◑ Static-validated).
- **Round-trip fixtures** — ODCS ⇄ OLC conversion examples as executable tests.

## Principles

- **Executable over descriptive.** A field earns its place if a framework can *act* on it.
- **Lean native vocabulary.** Accept aliases (e.g. ODCS names) on import; keep the native surface small.
- **Honest status.** Never label a provider ✅ Live unless the contracts actually ran and materialized tables there.
- **The contract is the invariant.** Backend-specific behavior belongs in frameworks, not in the contract.
