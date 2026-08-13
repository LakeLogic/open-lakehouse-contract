---
description: Validate this repo's Open Lakehouse Contracts (*.olc.yaml) against the JSON Schema
argument-hint: "[contract.olc.yaml ...]  (default: all **/*.olc.yaml)"
allowed-tools: Bash(olc:*), Bash(python:*), Read, Edit
---
Validate the project's Open Lakehouse Contracts against the schema — structural check
only, no runtime required.

!`olc validate $ARGUMENTS`

Then:
- If everything is **OK**, list which files passed and stop.
- If any file **FAILED**, read each reported `location: message`, open the offending
  `*.olc.yaml`, and edit it to satisfy the schema (the JSON Schema is at
  `schema/open-lakehouse-contract.schema.json`). Re-run to confirm it passes.

If `olc` is not installed, fall back to `python scripts/validate.py $ARGUMENTS`.
