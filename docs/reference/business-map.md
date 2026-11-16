# Business Map

A contract describes a dataset in technical terms: `pnr_segment`, `passenger_token`, `fct_trip`.
The **business map** puts it in the words the business uses — *Booked flight segment*, *Passenger*, *Trip* — and
says how those things relate: *Rider books Trip*.

OLC keeps the two apart, the same way it keeps [data products](data-products.md) apart from contracts:

- a **concept** is **defined once**, in its domain's `_domain.yaml` (`concepts:`);
- a **contract** **references** it by name (top-level `entity`, and `identifies` on a field) — it never copies the definition.

Everything in the business map is optional. A contract with no `entity` is valid; a domain with no `concepts` is valid.

## Defining concepts

```yaml
# _domain.yaml
domain: marketplace

concepts:
  Trip:                                   # the business name — the key contracts refer to
    definition: One ride from pickup to drop-off, requested by a rider and driven by a driver.
    identifier: trip_id                   # the column that identifies one instance
    also_called: [ride, journey]          # other names people use, incl. the old technical one
    not_to_be_confused_with: Booking — a trip that has been requested but not yet started.
    example: "Trip 8F2A: Lisbon airport to Baixa, 14 km"
  Rider:
    definition: A person who requests trips.
    identifier: rider_id

relationships:
  - {from: Rider, verb: books, to: Trip, cardinality: one_to_many}
  - {from: Driver, verb: drives, to: Trip, cardinality: one_to_many}

story:                                    # optional · the business process, in order
  actors: [Rider, Driver]
  steps:
    - {id: request, actor: Rider,  text: Rider requests a trip, concepts: [Trip]}
    - {id: accept,  actor: Driver, text: Driver accepts the trip, after: [request]}
    - {id: cancel,  actor: Rider,  text: Rider cancels, after: [request], kind: branch}
```

| Field | Rules |
|---|---|
| `concepts.<name>` | The business name. Contracts refer to this exact string. Rename it the way you rename an id: update the contracts that refer to it in the same change. |
| `definition` | One or two plain sentences a business reader would agree with. |
| `identifier` | One column name. Optional; when present it is how the map links contracts to the concept. |
| `also_called` | Other names, including the technical one a rename replaced (`pnr_segment`), so search and older documents still find it. |
| `relationships[].verb` | A plain verb, read `from verb to`: *Rider books Trip*. |
| `relationships[].cardinality` | `one_to_one`, `one_to_many`, `many_to_one`, `many_to_many`, `unknown`. `unknown` is a real answer — never replace it with a guess. |
| `story.steps[].kind` | `step` (default), `branch` (an alternative to the steps sharing its `after`), `gap` (a step the business has that no contract records yet). |

Validation checks that story step ids are unique, that every `after` names a step in the story, and that every
`actor` is one of `actors`. `concepts`, `relationships` and `story` are **domain-only**: a `_system.yaml` does not
declare them.

## Referencing a concept from a contract

```yaml
info:
  title: silver_trips
  domain: marketplace
entity: Trip                        # TOP LEVEL, not under info · this contract records Trips
model:
  fields:
    - {name: trip_id,   type: string}
    - {name: rider_id,  type: string, identifies: Rider}
    - {name: driver_id, type: string, identifies: Driver}
    - {name: payer_id,  type: string, identifies: Customer, role: payer}   # one concept, several roles
```

- `entity` (top level) names the concept the contract **represents** — one per contract.
- `identifies` on a field names the concept that column **points at**. `role` says which part it plays when one
  concept appears more than once (`payer`, `driver`).
- Both are names in the owning domain's `concepts`. A name that is not defined there is a gap to fix, not an error the
  validator raises: the domain file and the contract are often changed by different people.

## Agreed versus suggested

Tools may **infer** a map from what is already in the contracts — keys and columns that recur across tables, foreign
keys, Gold dimensions. An inferred concept or link is a **suggestion**. It becomes **agreed** only when it is written
into the domain file (or a contract's `entity` / `identifies`) and that change is merged. So:

- the domain file holds only what people agreed; nothing is written to it automatically;
- a suggested name, definition or relationship is proposed as a pull request against `_domain.yaml`, and merging it is
  the approval;
- a proposal edits only the `concepts:` / `relationships:` / `story:` blocks and leaves the rest of the file —
  comments, headers, ordering — untouched.

Two inference results are worth naming because they change what a map shows:

- **Shared key.** An identifier carried by several contracts with no table of its own (`record_locator`,
  `aircraft_registration`) is still a business thing. Tools may suggest it as a concept; when a concept with that name
  is agreed in the domain file, it takes over the key.
- **Calendar.** A date dimension (keyed on `date_key`) joins to almost everything. It is not a business relationship,
  so maps should not draw it as one.

## Exports

A business map is a small graph: concepts are classes, relationships are object properties, `definition` is a
comment and `also_called` are alternative labels. It maps directly onto RDF/OWL (Turtle) and onto a glossary.
Exporters should take only **agreed** content, or mark suggestions explicitly.
