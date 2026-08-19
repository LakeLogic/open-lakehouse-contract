---
title: CLI
description: The `olc` command — validate contracts against the spec and install agent integrations, with zero framework dependency.
---

# CLI (`olc`)

The `olc` command is the **standalone, dependency-free** way to work with Open Lakehouse
Contracts. It validates any `*.olc.yaml` against the public JSON Schema and installs
agent integrations — no runtime, no cloud, no framework required.

```bash
pip install open-lakehouse-contract
olc --version
```

**Why it matters**

- **A gate you can trust in CI.** `olc validate` fails on the things that silently rot a
  contract estate — schema violations, *and* a discovery run that finds **zero**
  contracts (a misconfigured path that would otherwise pass green).
- **Portable by construction.** It checks against the JSON Schema, so the same guarantee
  holds in any language or pipeline — the contract is the standard, not the tool.
- **Agent-ready in one step.** `olc init` drops in assistant integrations safely, never
  overwriting divergent files without your say-so.

---

## `olc validate`

Validate explicit files, or recursively discover every contract under a directory.

```bash
olc validate contracts/orders.olc.yaml        # one or more files
olc validate --root contracts                 # discover recursively
olc validate --root contracts --output json   # machine-readable for CI
```

Discovery **fails when no contracts are found**, so a mistyped path can't let a CI job
pass silently — use `--allow-empty` only when an empty directory is genuinely expected.
The YAML loader also rejects duplicate keys rather than silently keeping the last one.

Point at a specific schema (a pinned version, or a URL) with `--schema`:

```bash
olc validate contracts/orders.olc.yaml --schema schema/open-lakehouse-contract.schema.json
```

Exit code `0` = every contract valid; non-zero = at least one failure. That's the whole
contract with CI.

---

## `olc init`

Install assistant integrations (e.g. Claude, Codex) into a project, safely.

```bash
olc init --list                       # show what can be installed
olc init --tools claude,codex --dry-run
olc init --tools claude,codex
```

Existing **identical** files are left untouched. If a destination file **differs**, the
whole install stops before writing anything — review and merge it yourself, or pass
`--force` when replacement is intentional. No surprise overwrites.

---

## Where `olc` ends and LakeLogic begins

`olc` validates and scaffolds a **single portable contract**. To *run* contracts
(validate + quarantine + materialize across engines), or to validate the **mesh
registry** that supplies contracts their shared defaults, use the LakeLogic reference
framework and its `lakelogic` CLI — see
[LakeLogic CLI](https://lakelogic.github.io/LakeLogic/cli/). The boundary is deliberate:
the standard stays small and portable; the framework does the heavy lifting.
