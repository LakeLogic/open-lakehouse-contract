---
title: Compliance
description: The `compliance` block — an open, free-form slot for classification and controls (regulatory scope, retention, residency, approvals) that a runtime and downstream governance can act on.
---

# Compliance (`compliance`)

`compliance` is a **free-form object** — a deliberately open slot for **classification and controls** that belong to the data product but aren't part of its shape: regulatory scope, retention, residency, ownership approvals, and the like. The schema places **no constraints** on its keys (`additionalProperties: true`), so you attach whatever your organisation's governance model needs.

These keys are **illustrative, not a schema** — pick what your governance model uses:

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
  retention: { period: 400d, basis: legal }
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

## Why it's free-form (and not typed)

Compliance vocabularies differ wildly between organisations and regimes — pinning a fixed schema would either be too narrow or too vague. OLC keeps the **shape** fields strict (see [Model & keys](schema.md#schema-keys)) and leaves `compliance` open, so it's a durable place to carry governance metadata without forcing a one-size-fits-all structure.

## How it's used

- **It travels with the contract** — the same file that defines the data product carries its compliance context, so the two can't drift apart.
- **PII is separate and enforced.** Field-level `pii` / `masking` are *acted on at runtime* (see [Security & PII](security.md)); `compliance` is the broader classification/controls layer around them.
- **Downstream governance reads it.** A conforming framework and any governance/audit layer can key off these values (e.g. block a run whose `data_residency` doesn't match the target, or surface `retention` in an audit view). The open spec defines the slot; enforcement is the runtime's job.

!!! note "Keep enforceable rules in the enforceable blocks"
    `compliance` is metadata, not a gate. If a rule must *fail a run*, express it where the runtime enforces it — a [quality rule](quality.md), a field-level `masking`, or a [service-level](slo.md) threshold — and use `compliance` to record the *why* alongside it.
