# Data Products

A **contract** describes one dataset. A **data product** is a useful offering with a defined purpose and an
accountable owner, usually published as several contracted outputs — tables, views, APIs or semantic models.

OLC keeps the two apart:

- the product is **defined once**, in its domain's `_domain.yaml` (`products:`);
- each contract **references** the product that publishes it (`info.data_product`), by a stable id.

## Defining a product

```yaml
# _domain.yaml
domain: real_estate

products:
  - id: property_performance          # required · lowercase id, set once, never changed
    name: Property Performance        # required · display name, safe to rename
    description: Monthly property income, expenses and operating performance.
    owner: property_data_team         # optional · falls back to the domain's ownership
    lifecycle: active                 # proposed (default) | active | deprecated | retired
    expected_outputs:                 # optional · declare when completeness matters
      - id: monthly_property_income   # required · unique within the product
        name: Monthly Property Income
        kind: table                   # table (default) | view | api | semantic_model
        required: true                # default true
      - id: occupancy_model
        name: Occupancy semantic model
        kind: semantic_model
        required: false
```

| Field | Rules |
|---|---|
| `id` | `^[a-z][a-z0-9_]{1,62}$`. Unique within the domain. The value contracts reference — never change it. |
| `name` | Required. Change freely; no contract refers to it. |
| `lifecycle` | `proposed`, `active`, `deprecated`, `retired`. Defaults to `proposed`. |
| `expected_outputs[].id` | Same id format. Unique within the product. |
| `expected_outputs[].kind` | `table`, `view`, `api`, `semantic_model`. |
| `expected_outputs[].required` | Whether the product is incomplete without it. |

Unknown keys are rejected by strict validation, except `x-` vendor extensions. An empty `products:` means none.

## Referencing a product from a contract

```yaml
info:
  title: gold_property_monthly_income
  domain: real_estate
  data_product: property_performance            # the product that publishes this output
  data_product_output: monthly_property_income  # optional · which expected output this implements
```

- `info.data_product` means **the product that publishes this contracted output** — not every product that uses it.
- Both values are ids in the same format as above. `data_product_output` requires `data_product`.
- A contract without `data_product` is valid. Supporting and unassigned datasets are legitimate; whether a contract
  must belong to a product is a policy your platform applies, not a schema rule.

## Shared datasets

A dataset belongs to the product that publishes it, or to none. When another product depends on it — a shared
dimension, a common silver table — that is a **lineage** relationship (`upstream_contracts`), not a second
membership.

## Environments

A product is defined once and means the same thing in every environment. Whether an output exists, and what evidence
it reports, varies by environment — that is observed, not declared.

## What a validator checks, and what it cannot

Strict validation checks each document on its own: id formats, allowed values, unique ids, unknown keys. Checks that
need the whole registry — a contract referencing a product id no domain defines, a required output no contract
implements, an output claimed by two contracts — belong to the platform that reads all documents together.
