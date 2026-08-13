# OLC agent integrations

**Portable across every AI agent.** The same Open Lakehouse Contract workflow — the verbs
`discover → contract → review → validate → impact` — exposed through each assistant's
native mechanism. This mirrors [OpenSpec](https://github.com/Fission-AI/openspec)'s
approach (one common set of verbs, per-assistant wrappers) and is **open**: it needs no
LakeLogic Cloud, only the schema + the `olc` CLI.

## Layout

```
skills/
  claude/                 # Claude Code (reference integration)
    commands/olc/*.md     -> installed to <project>/.claude/commands/olc/   (slash commands)
    skills/olc/SKILL.md   -> installed to <project>/.claude/skills/olc/     (Agent Skill)
  codex/                  # OpenAI Codex / ChatGPT-in-the-terminal
    prompts/olc-*.md      -> installed to <project>/.codex/prompts/         (custom prompts)
  # cursor / copilot / gemini / windsurf — on the roadmap
```

## Install

```bash
pip install -e .                    # provides the `olc` CLI (validate + init)
olc init --tools claude,codex       # copies the integrations into ./.claude and ./.codex
olc init --list                     # see available integrations
```

## Test it

**Claude Code** — in a repo that has `*.olc.yaml` contracts:

```
/olc:validate                       # validate them (works today — schema only)
/olc:contract "daily revenue by city from Stripe"
/olc:review                         # breaking-change gate for the current diff
```

**ChatGPT / Codex** — the same verbs as Codex prompts (`/olc-validate`, `/olc-contract`, …),
which run `olc validate` in the shell just like Claude does.

**ChatGPT (web)** — no shell, so use a *Custom GPT*: upload
`schema/open-lakehouse-contract.schema.json` as knowledge and paste the SKILL.md content
as instructions. It can then author schema-valid contracts (paste them back to validate
locally with `olc validate`).

## The verbs

| Verb | What it does |
|---|---|
| `discover` | Analyse the repo; propose contracts for the data products it finds |
| `contract` | Generate/update the contract for one data product (schema-valid) |
| `review`   | Compare the current change to the contracts; flag breaking changes (the merge gate) |
| `validate` | Structural check against the JSON Schema (no runtime) |
| `impact`   | Change-impact analysis across schema, consumers, and SLOs |

The verbs are identical across assistants; only the wrapper differs. Same intent, every tool.

## Open vs. enterprise

The integrations, the `olc` CLI, and the reference runtime (**LakeLogic Core**) are
**open** — no cloud dependency. **LakeLogic Cloud** is the enterprise layer *around* the
standard (estate-wide context, telemetry history, Jira / org graph, policy & trust,
collaboration, managed agents). The open standard is the entry point; the cloud is an
enterprise convenience, never a gate on adoption.
