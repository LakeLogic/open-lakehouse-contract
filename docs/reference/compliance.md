---
title: Compliance
description: The `compliance` block — an open, free-form slot for classification and controls (regulatory scope, retention, residency, approvals) that a runtime and downstream governance can act on.
---

# Compliance (`compliance`)

`compliance` is a **free-form object** — a deliberately open slot for **classification and controls** that belong to the data product but aren't part of its shape: regulatory scope, retention, residency, ownership approvals, and the like. The schema places **no constraints** on its keys (`additionalProperties: true`), so you attach whatever your organisation's governance model needs — with one exception, [`retention`](#retention), which is typed.

Apart from `retention`, these keys are **illustrative, not a schema** — pick what your governance model uses:

```yaml
compliance:
  # ── Regulatory scope ──
  regulations: [GDPR, CCPA, HIPAA]        # what applies to this product
  lawful_basis: contract                  # GDPR processing basis
  purpose: "billing + fraud analytics"    # why the data is held

  # ── Classification & sensitivity ──
  classification: confidential            # public | internal | confidential | restricted
  contains_pii: true
  contains_phi: false
  pii_categories: [email, name, location]

  # ── Residency & retention ──
  data_residency: eu-west                 # where it may live
  retention: { period: P6Y, column: signup_date, basis: legal }   # typed: see below
  legal_hold: false
  right_to_erasure: true                  # supports GDPR/CCPA deletion requests

  # ── Ownership & approvals ──
  data_owner: sales-analytics@acme.com
  steward: jane.doe@acme.com
  approved_by: data-governance@acme.com
  approval_ref: GOV-1423                  # link to the sign-off ticket

  # ── Controls & audit ──
  controls: { encryption_at_rest: true, masking_required: true }
  audit: { log_access: true }
  frameworks: [SOC2, ISO27001]            # certifications in scope

  # …any org-specific key — the schema places no constraints
```

## Retention

`compliance.retention` is the one **typed** key: this contract's own retention period. It **overrides the domain's period for the contract's layer** (`retention: {bronze: P7D, silver: P90D, gold: P7Y}` in `_domain.yaml`), so one table can be held to a different period than the rest of its layer — driver records six years, trips ninety days.

```yaml
compliance:
  retention:
    period: P6Y                 # required: ISO 8601 (P90D, P6Y, P1Y6M) or short form (400d, 6y)
    column: signup_date         # optional: the column whose OLDEST value measures a record's age
    starts: record_created      # optional: record_created | relationship_ended | custom
    basis: "Tax: 6 years from signup"   # optional: why this period applies
```

| Key | Required | Meaning |
|---|---|---|
| `period` | yes | How long a record may be kept. ISO 8601, or the short form `400d` / `12w` / `18m` / `6y`. |
| `column` | no | The column whose oldest value is the record's age. Omitted: the runtime's default age columns. |
| `starts` | no | When the clock starts. Many obligations run from the **end** of a relationship (six years after an account closes), which a creation date cannot measure — `relationship_ended` records that, so a reviewer does not read the check as more than it is. |
| `basis` | no | Why this period applies: `legal`, `contract`, or a sentence. |

**Precedence:** the contract's `compliance.retention.period`, else the domain's period for the contract's layer, else no retention promise. A misspelled key or an invalid period is rejected, because a typo here would silently fall back to the layer's period.

## Why it's free-form (and not typed)

Compliance vocabularies differ wildly between organisations and regimes — pinning a fixed schema would either be too narrow or too vague. OLC keeps the **shape** fields strict (see [Model & keys](schema.md#schema-keys)) and leaves `compliance` open, so it's a durable place to carry governance metadata without forcing a one-size-fits-all structure.

## How it's used

- **It travels with the contract** — the same file that defines the data product carries its compliance context, so the two can't drift apart.
- **PII is separate and enforced.** Field-level `pii` / `masking` are *acted on at runtime* (see [Security & PII](security.md)); `compliance` is the broader classification/controls layer around them.
- **Downstream governance reads it.** A conforming framework and any governance/audit layer can key off these values (e.g. block a run whose `data_residency` doesn't match the target, or surface `retention` in an audit view). The open spec defines the slot; enforcement is the runtime's job.

!!! note "Keep enforceable rules in the enforceable blocks"
    `compliance` is metadata, not a gate. If a rule must *fail a run*, express it where the runtime enforces it — a [quality rule](quality.md), a field-level `masking`, or a [service-level](slo.md) threshold — and use `compliance` to record the *why* alongside it.
