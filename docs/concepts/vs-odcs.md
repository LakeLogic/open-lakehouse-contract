# OLC & ODCS

OLC **complements the [Open Data Contract Standard (ODCS)](https://github.com/bitol-io/open-data-contract-standard)** — it doesn't compete with it. ODCS is the excellent, widely-adopted standard for *describing* a data contract; OLC adds the *executable, lakehouse-scoped* layer that runs it. They're two points on the same axis, with a round trip between them, and the reference runtime is deliberately ODCS-interoperable so you never have to choose.

!!! tip "The short version"
    Use **ODCS** to publish and agree on a contract across teams and catalogs. Use **OLC** to *run* it — validate, quarantine, mask, materialize. Import ODCS → run as OLC → export ODCS; nothing is lost either direction.

## The distinction

| | ODCS | Open Lakehouse Contract |
|---|---|---|
| **Primary purpose** | *Describe* a data contract — a shared, human/tool-readable agreement | *Execute* a data product — validate, quarantine, mask, materialize |
| **Scope** | Schema-centric (plus SLAs, terms, quality descriptions) | Whole lakehouse surface: schema **+ quality + quarantine + PII + lineage + materialization + SLOs + keys + transforms** |
| **Relationship to a runtime** | Runtime-agnostic description | Emitted from a reference runtime; the file *runs* |
| **Best at** | Cataloguing, discovery, governance sign-off, cross-org agreement | Building and enforcing the pipeline that produces the data |

Think of ODCS as the **descriptive, schema-scoped** contract for the whole data-agreement world, and OLC as the **executable, lakehouse-scoped** contract for building the data product — with a round trip between them.

## Round-trip interop

The reference runtime imports ODCS and can export back to it, so the two aren't a fork in the road:

```python
from lakelogic.core.models import DataContract

contract = DataContract.from_odcs("orders.odcs.yaml")   # ingest an ODCS contract
# ... run it: validate, quarantine, materialize ...
odcs = contract.to_odcs()                               # emit ODCS back out
```

There's also a CLI export (`lakelogic export-odcs`) in the reference runtime.

## Native vocabulary, ODCS aliases

OLC keeps its **native vocabulary lean** — the field names that map directly to executable behavior. Where ODCS uses different names for the same concept, they're accepted as **aliases** on import, so an ODCS-authored contract validates and runs without a manual rewrite. You don't have to choose one dialect at authoring time.

## When to use which

- **Publishing an agreement across teams or orgs, feeding a catalog, or getting governance sign-off?** ODCS is the lingua franca — describe it there.
- **Building the data product — enforcing quality, masking PII, materializing to a lakehouse, and wanting the contract to *be* the pipeline?** Author (or import) an OLC and run it.
- **Both?** Import ODCS → run as OLC → export ODCS. The descriptive and executable worlds stay in sync through the round trip.

!!! tip "Not either/or"
    OLC being broader than ODCS is a *scope* statement, not a value judgment. ODCS is excellent at what it targets. OLC targets the executable superset needed to actually produce and govern the dataset the contract describes.
