# Why Pydantic

OLC has three layers — the **specification** (what the fields mean), its **JSON Schema** (machine-readable structure), and the **reference implementation** (executable behaviour). The JSON Schema is **not hand-written**: it's *derived* from the reference implementation's [Pydantic](https://docs.pydantic.dev) models. That's a deliberate choice — and the thing to be careful about is *not* to read it as "the Pydantic models **are** the specification." They're the reference implementation the schema is generated from; the spec is separable, and another runtime in another language could implement it.

## The rot problem

Hand-maintained schemas rot. The document says one thing, the implementation does another, and every release widens the gap until the schema is folklore. The usual "fix" — manually keeping a schema file in sync with N implementations — is exactly how the drift happens.

OLC removes that gap for the *machine-readable* layer: the **JSON Schema is generated from the reference models**, so the structural form can't drift from a working runtime:

```bash
python scripts/generate_schema.py     # schema/ ← DataContract.model_json_schema()
```

```python
# scripts/generate_schema.py (essence)
from lakelogic.core.models import DataContract   # the reference implementation
schema = DataContract.model_json_schema()        # Pydantic → JSON Schema, for free
```

The published schema can't describe something the reference runtime can't run, because it's *emitted by* that runtime's own type definitions. The machine-readable layer tracks a working implementation instead of a hand-kept document — while the specification itself stays runtime-neutral.

!!! note "Reference implementation ≠ specification"
    The Pydantic models are the **reference implementation**, not the standard. The standard is *what the fields mean* (the [field reference](../reference/schema.md)) plus its structural form (the JSON Schema). Generating the schema from a real runtime is a pragmatic way to keep them honest — not a claim that one vendor's Python classes are the spec. See [What is OLC? → independent of the runtime](what-is-olc.md#the-contract-is-independent-of-the-runtime).

## What Pydantic gives OLC

- **A typed reference model.** `DataContract`, `Materialization`, `Quarantine`, `Link`, and the rest are ordinary Python classes with typed fields and validators — the *reference* model; the JSON Schema and the runtime behavior both fall out of them.
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
