# Changelog

All notable changes to the **Open Lakehouse Contract (OLC)** are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---
## [0.6.0] — 2026-08-23

### Added

- Update deduplication transformation and add upstream sources support

### Build

- **release**: Exit cleanly when there is nothing to bump

### Documentation

- Update README and documentation for clarity and consistency
- Update changelog for v0.4.0

### Styling

- **conformance**: Silence E402 on imports deferred past _require guards
## [0.4.0] — 2026-08-19

### Added

- Add self-referential consumers field to DownstreamConsumer model

### CI/CD

- **docs**: Deploy mkdocs site to GitHub Pages on push to main

### Documentation

- **providers**: Mark private-repo providers as 'Coming soon'
- Update changelog for v0.3.1

### Fixed

- **release**: Annotate the re-attached tag so --follow-tags pushes it
## [0.3.1] — 2026-08-18

### CI/CD

- **publish**: Switch to PyPI Trusted Publishing (OIDC)
- Skip runtime-conformance until LAKELOGIC_REF is pinned
## [0.3.0] — 2026-08-18

### Added

- Add changelog generation workflow and update related configurations
- Add new conformance cases for dataset uniqueness, external logic extraction, regex extraction, and SCD2 dimension handling
## [0.2.0] — 2026-08-15

### Added

- **skills**: Expand agent integrations to 11 assistants
- **skills**: Agent integrations for 7 assistants (add Cursor/Copilot/Gemini/Windsurf/Cline)
- Implement strict OLC v1 model with nested key validation
- Real olc CLI + Claude/Codex agent integrations (skills/)

### Build

- Self-contained wheel + PyPI publish workflow

### Documentation

- **agent-workflow**: Validate against contract-generated synthetic data (no real data needed)
- **providers**: Define RideFlow on first mention
- **quality**: Expand dataset rules with quality-SLO use-case scenarios
- **quality**: Make Validation & Quality SQL-centric + fix shorthand keys
- **readme**: Update materialization location for clarity in sales domain
- **readme**: Enhance SQL rules section with business shorthands and multi-source support for clarity
- **readme**: Enhance contract details with additional fields and validation rules for completeness and correctness
- **readme**: Clickable engine/format links under the banner
- **readme**: Richer banner + link fixes + trim badges
- **readme**: Restyle in the spec-framework format (OpenSpec-aligned)
- **reference**: Link each field-reference row to its deep-dive page
- **theme**: Follow OS colour preference (prefers-color-scheme)
- **theme**: Default to the dark (near-black) scheme
- **theme**: Use LakeLogic logo + fix stray mermaid 'Syntax error' bomb
- **theme**: Force mermaid diagrams full-width (override inline max-width)
- **theme**: Render mermaid diagrams at full content width (bigger, more legible)
- **transformation**: Accurate copy-pasteable example for every op
- Engines compose on one platform + fix why-pydantic mermaid
- Sharpen positioning, add full-contract reference, rename runtime→framework
- Update README, banner, and index descriptions for clarity and consistency
- Drop the OpenSpec star count (~65k) — keep the reference, not the metric
- Adopt the LakeLogic doc-site design system
- External_logic — spectrum framing + concrete PySpark sample
- Add External Logic reference (Spark, notebooks, stored procs, dbt)
- How OLC works alongside greenfield & brownfield platforms
- Add plain-language 'AI Data Agents' on-ramp
- OLC portable across AI agents too — data-native verbs, persistent intent, open integration
- Actively embrace ODCS + add a runtime-free CI validator
- Sharpen OLC as an independent standard (spec vs runtime, scope, dialects, CI gate)
- Give Lineage its own page + add graph & Airflow-style DAG lineage
- Add Agent Workflow — spec-driven data products for AI agents
- Frame OLC as complementing ODCS + cite the spec-driven movement (OpenSpec)
- Add Execution Order page capturing pre & post
- Emphasize SQL-native — transformation ops show SQL variant first
- Comprehensive lifecycle authoring reference (every option) + library map
- Full mkdocs-material site + Terraform-style provider matrix
---

<!-- Link definitions -->
[0.6.0]: https://github.com/LakeLogic/open-lakehouse-contract/compare/v0.4.0...v0.6.0
[0.4.0]: https://github.com/LakeLogic/open-lakehouse-contract/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/LakeLogic/open-lakehouse-contract/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/LakeLogic/open-lakehouse-contract/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/LakeLogic/open-lakehouse-contract/releases/tag/v0.2.0

