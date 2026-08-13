# Getting Started

An Open Lakehouse Contract is just a YAML file plus a JSON Schema to validate it against. You can start using OLC with nothing but a schema validator — and run it with the reference runtime when you're ready.

## 1. Validate a contract against the spec

The spec is a single JSON Schema (Draft 2020-12): [`schema/open-lakehouse-contract.schema.json`](https://github.com/LakeLogic/open-lakehouse-contract/blob/main/schema/open-lakehouse-contract.schema.json). Validate any OLC file against it with any JSON-Schema tool, in any language.

```bash
pip install jsonschema pyyaml
python tests/conformance.py     # validates examples/ + tests/ against the schema
```

Expected output:

```
  PASS  (expect valid)   examples/orders.olc.yaml
  PASS  (expect valid)   tests/valid/minimal.yaml
  PASS  (expect invalid) tests/invalid/fields_not_a_list.yaml
  PASS  (expect invalid) tests/invalid/info_wrong_type.yaml

OK  - all conformance checks passed
```

See the [Conformance Suite](reference/conformance.md) for how the corpus is structured.

## 2. Write your first contract

The smallest valid contract is a `version` plus an `info` block:

```yaml
version: 1.0.0
info:
  title: Orders
  table_name: orders
  target_layer: silver
model:
  fields:
    - { name: order_id, type: integer, required: true }
    - { name: amount,   type: float,   required: true }
primary_key: [order_id]
```

Add governance as you need it — quality rules, PII masking, lineage, materialization:

```yaml
quality:
  row_rules:
    - { name: positive_amount, sql: "amount > 0" }
  dataset_rules:
    - { name: order_id_unique, unique: order_id }
lineage:
  enabled: true            # provenance columns injected on every row
materialization:
  strategy: merge          # converge the target to the declared shape
  format: iceberg
```

The full vocabulary is in the [Field Reference](reference/schema.md); a complete annotated example is [`examples/orders.olc.yaml`](https://github.com/LakeLogic/open-lakehouse-contract/blob/main/examples/orders.olc.yaml).

## 3. Execute it with the reference runtime

The contract becomes *executable* through a conforming runtime. [LakeLogic](https://lakelogic.org) is the reference implementation:

```bash
pip install lakelogic
```

```python
from lakelogic import DataProcessor

proc = DataProcessor("orders.olc.yaml", engine="duckdb")   # or "spark" / "polars"
good, bad = proc.run(source_dataframe)                     # validate + quarantine
proc.materialize(good, bad)                                # write per `materialization`
```

The *same* contract runs unchanged on another engine, table format, or platform — that's the whole point. Pick your backend on the [Providers](providers/index.md) pages.

## 4. Keep the schema honest

The JSON Schema is **generated** from the reference runtime's typed models — never hand-edited — so the standard tracks a working implementation instead of rotting:

```bash
pip install lakelogic
python scripts/generate_schema.py     # schema/ ← the Pydantic DataContract model
```

Read why that matters in [Why Pydantic](concepts/why-pydantic.md).
