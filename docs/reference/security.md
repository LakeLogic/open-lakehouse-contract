# Security & PII

Sensitivity classification and masking travel **with the schema** — declared on the field, not bolted on in a separate policy file. Because they live in `model.fields[]` (`FieldDefinition`), they move with the contract across every engine and platform, and downstream consumers inherit them through lineage.

!!! abstract "Powered by"
    Field governance is defined on the **Pydantic** `FieldDefinition` model. Masking transforms execute in the active engine (**PySpark** / **duckdb** / **polars**), so a masking policy declared once is applied identically everywhere. Tokenization can be delegated to an external vault via `pii_vault`.

## Classifying a field

```yaml
model:
  fields:
    - name: customer_email
      type: string
      pii: true                 # personally identifiable
      masking: partial          # how to mask it in outputs
      masking_format: email     # format-aware masking (keep domain, hide local part)
      classification: confidential
      security_groups: [pii-readers]
    - name: ssn
      type: string
      pii: true
      masking: hash
      pii_vault: "customers"    # tokenize/store in a named vault instead of in-table
    - name: diagnosis
      type: string
      phi: true                 # protected health info
      masking: redact
      sensitive: true
```

## The governance fields

| `FieldDefinition` field | Purpose |
|---|---|
| `pii` | Marks the field as personally identifiable information. |
| `phi` | Marks protected health information (HIPAA-style). |
| `sensitive` | General sensitivity flag (beyond PII/PHI) — e.g. commercial secrets. |
| `classification` | A label such as `public` / `internal` / `confidential` / `restricted`. |
| `masking` | The masking strategy applied on write/read (see below). |
| `masking_format` | Format-aware masking (e.g. `email`, `phone`, `credit_card`) so masked values stay realistic. |
| `pii_vault` | Name of an external vault to tokenize the value into, instead of storing it in the table. |
| `security_groups` | Groups permitted to see the unmasked value — drives row/column access downstream. |

## Masking strategies

`masking` selects how a sensitive value is obscured. Common strategies:

| Value | Effect |
|---|---|
| `partial` | Reveal part, hide the rest (`a***@example.com`). Combine with `masking_format` for realistic output. |
| `hash` | One-way hash (deterministic — joins still work, values are opaque). |
| `redact` | Replace with a fixed token (`***`). |
| `tokenize` | Replace with a token backed by `pii_vault` (reversible only via the vault). |
| `null` | Null the value entirely. |

## Masking is lineage-aware

When a masked field flows into a downstream dataset, the masking follows it. A downstream contract doesn't have to re-declare the policy — the effective masking is resolved through lineage, so a field that was `pii: true, masking: partial` upstream stays masked downstream unless a consumer is explicitly authorized. Pair with `security_groups` to control who resolves the unmasked value.

!!! tip "PII and LLM extraction"
    When feeding rows to an LLM (see [Unstructured / LLM Extraction](extraction.md)), set `extraction.redact_pii_before_llm: true` and list `extraction.pii_fields` so identifiers are stripped **before** the prompt leaves your environment. Field-level `pii: true` is the source of truth for what counts as PII.

## Access & audit

- `security_groups` on a field expresses **who may see it unmasked** — the runtime and the SaaS control plane enforce this as column-level access.
- `classification` (field-level) and `info.classification` (contract-level) drive catalog-wide policy and audit.
- Every masking/quarantine decision is captured in lineage + audit, so "who could see this, and was it masked" is answerable after the fact.
