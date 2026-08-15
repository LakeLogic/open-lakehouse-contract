## [0.2.0] - 2026-08-15

### 🚀 Features

- Real olc CLI + Claude/Codex agent integrations (skills/)
- *(skills)* Agent integrations for 7 assistants (add Cursor/Copilot/Gemini/Windsurf/Cline)
- *(skills)* Expand agent integrations to 11 assistants
- Implement strict OLC v1 model with nested key validation

### 💼 Other

- Self-contained wheel + PyPI publish workflow
- Version 0.1.0 → 0.2.0

### 📚 Documentation

- Full mkdocs-material site + Terraform-style provider matrix
- Comprehensive lifecycle authoring reference (every option) + library map
- *(transformation)* Accurate copy-pasteable example for every op
- *(reference)* Link each field-reference row to its deep-dive page
- Emphasize SQL-native — transformation ops show SQL variant first
- Add Execution Order page capturing pre & post
- *(quality)* Make Validation & Quality SQL-centric + fix shorthand keys
- *(providers)* Define RideFlow on first mention
- Frame OLC as complementing ODCS + cite the spec-driven movement (OpenSpec)
- Add Agent Workflow — spec-driven data products for AI agents
- Give Lineage its own page + add graph & Airflow-style DAG lineage
- *(quality)* Expand dataset rules with quality-SLO use-case scenarios
- *(readme)* Restyle in the spec-framework format (OpenSpec-aligned)
- Sharpen OLC as an independent standard (spec vs runtime, scope, dialects, CI gate)
- Actively embrace ODCS + add a runtime-free CI validator
- OLC portable across AI agents too — data-native verbs, persistent intent, open integration
- *(agent-workflow)* Validate against contract-generated synthetic data (no real data needed)
- Add plain-language 'AI Data Agents' on-ramp
- How OLC works alongside greenfield & brownfield platforms
- Add External Logic reference (Spark, notebooks, stored procs, dbt)
- External_logic — spectrum framing + concrete PySpark sample
- Adopt the LakeLogic doc-site design system
- Drop the OpenSpec star count (~65k) — keep the reference, not the metric
- *(theme)* Render mermaid diagrams at full content width (bigger, more legible)
- *(theme)* Force mermaid diagrams full-width (override inline max-width)
- *(theme)* Use LakeLogic logo + fix stray mermaid 'Syntax error' bomb
- *(theme)* Default to the dark (near-black) scheme
- *(theme)* Follow OS colour preference (prefers-color-scheme)
- *(readme)* Richer banner + link fixes + trim badges
- *(readme)* Clickable engine/format links under the banner
- Update README, banner, and index descriptions for clarity and consistency
- *(readme)* Enhance contract details with additional fields and validation rules for completeness and correctness
- *(readme)* Enhance SQL rules section with business shorthands and multi-source support for clarity
- *(readme)* Update materialization location for clarity in sales domain
- Sharpen positioning, add full-contract reference, rename runtime→framework
- Engines compose on one platform + fix why-pydantic mermaid

### ⚙️ Miscellaneous Tasks

- Apache-2.0 license + README banner
