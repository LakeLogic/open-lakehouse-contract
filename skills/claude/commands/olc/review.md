---
description: Review the current changes against applicable OLC contracts for breaking changes
allowed-tools: Bash(git:*), Bash(olc:*), Bash(python:*), Read, Glob, Grep
---
Act as the Open Lakehouse Contract **merge gate** for the current change.

1. **Gather context.** Find applicable contracts (`**/*.olc.yaml`) and the diff:
   !`git diff --stat`
   Then read the full diff for the changed data assets (`git diff`).
2. **Compare change vs. contract** for each affected data product, and flag **breaking**
   changes as a *diff of intent*:
   - **schema** — dropped / renamed / retyped fields, widened nullability
   - **quality** — removed or weakened rules
   - **materialization** — strategy change (e.g. `merge` → `append`), format change
   - **PII** — a field that lost `pii` / `masking`, or widened exposure
   - **keys / SLO / lineage** — changed `primary_key`, relaxed freshness, broken
     `upstream` / `downstream` edges
3. **Validate** the contracts still pass: !`olc validate`
4. **Verdict.** Output **PASS** or **FAIL** with the specific breaking items and the
   minimal contract or code edits to make the change safe.

The question you are answering is not "did the code change?" but "does the data product
still satisfy its contract?"
