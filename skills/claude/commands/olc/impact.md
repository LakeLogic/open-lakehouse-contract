---
description: Impact analysis for a proposed change to a data product
argument-hint: "\"add customer_segment to customer_360\""
allowed-tools: Read, Glob, Grep, Bash(git:*)
---
Analyse the impact of this proposed change: **$ARGUMENTS**

1. **Locate** the target data product's contract (`**/*.olc.yaml`) and its declared
   `downstream` consumers, `links`, and `upstream` edges.
2. **Determine what it touches** — schema (new / removed / retyped field), quality rules,
   PII classification, materialization, keys, or SLOs.
3. **Trace downstream** — which consumers (dashboards / models / exports in `downstream`,
   matched via `columns_used`) and which dependent contracts reference the affected
   columns.
4. **Report**:
   - what changes in the contract,
   - who is affected (and whether it is breaking),
   - the minimal set of contract edits to make the change safe,
   - and whether any `downstream[].sla` or SLO is put at risk.

This is a read-only analysis — propose, don't apply.
