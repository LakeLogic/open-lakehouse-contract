# Why Pydantic

The OLC spec is a JSON Schema. But that JSON Schema is **not hand-written** — it is *derived* from the reference runtime's [Pydantic](https://docs.pydantic.dev) models. This is a deliberate design decision, and it's what makes "open" honest here.

## The rot problem

Hand-maintained specs rot. The document says one thing, the implementation does another, and every release widens the gap until the spec is folklore. The usual "fix" — a spec committee that manually keeps a Word document in sync with N implementations — is exactly how the drift happens.

OLC inverts it. There is **one source of truth — the reference runtime's typed models** — and the spec is generated from it:

```bash
python scripts/generate_schema.py     # schema/ ← DataContract.model_json_schema()
```

```python
# scripts/generate_schema.py (essence)
from lakelogic.core.models import DataContract   # the reference implementation
schema = DataContract.model_json_schema()        # Pydantic → JSON Schema, for free
```

The spec can't describe something the runtime can't run, because the spec is *emitted by* the runtime's own type definitions. The standard tracks a working implementation instead of a document.

## What Pydantic gives OLC

- **A single typed source of truth.** `DataContract`, `Materialization`, `Quarantine`, `Link`, and the rest are ordinary Python classes with typed fields and validators. They *are* the model; the JSON Schema and the runtime behavior both fall out of them.
- **Language-neutral output.** `model_json_schema()` produces a standard **JSON Schema (Draft 2020-12)**. Any tool, in any language — Go, TypeScript, Rust, a CI linter — can validate OLC files without touching Python. The schema is the interop boundary.
- **Validation for free.** The same Pydantic models that define the shape also *parse and validate* it at runtime, with precise, structured errors ("`model.fields.2.type` is not a valid type") rather than a vague failure.
- **Evolvability.** Add a field to the model, regenerate, and the spec, the validator, and the runtime all move together in one commit. Versioning is a property of the model, not a manual reconciliation.

## The division of labour

```mermaid
flowchart TB
    subgraph Reference runtime (LakeLogic)
      M[Pydantic DataContract models]
    end
    M -->|model_json_schema()| S[open-lakehouse-contract.schema.json]
    S -->|validate, any language| A[Your tools / CI / agents]
    M -->|parse + execute| R[Runtime: validate · quarantine · materialize]
```

- **This repo** publishes the generated JSON Schema + a conformance corpus. It is vendor-neutral: any runtime can implement it.
- **[LakeLogic](https://lakelogic.org)** is the canonical reference runtime whose Pydantic models the schema is generated from.

That's the honest version of "open standard + reference implementation": the standard is a *file you can validate against in any language*, and it is provably in sync with a runtime because it was generated from that runtime's types.

## For agents, especially

A JSON Schema derived from strict types is the ideal target for an LLM: it can be used as a **structured-output / tool-call constraint**, so a model *generates a valid contract by construction* rather than emitting free text you hope parses. More on that in [Agent-Native](agent-native.md).
