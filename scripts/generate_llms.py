"""Generate docs/llms.txt and docs/llms-full.txt: the OLC standard in a form an LLM can follow.

    python scripts/generate_llms.py          # write both files
    python scripts/generate_llms.py --check  # exit 1 if either is stale

``llms.txt`` is the map: what OLC is, the rules a contract must follow to validate first time,
and links to the schema, reference pages, lint rules and an example. ``llms-full.txt`` is every
reference page and example concatenated, for an agent that wants it all in one fetch.

Facts that can drift (field names, source types, formats, transformation operations, the docs
pages) are read from the OLC model and ``mkdocs.yml`` at generation time, never typed here, and
CI fails when the committed files are stale (tests/test_llms_txt.py).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from olc.models import OLCContractV1  # noqa: E402
from olc.models._nested import SOURCE_TYPES, Transformation  # noqa: E402
from olc.models.source_options import SOURCE_FORMATS  # noqa: E402

DOCS = ROOT / "docs"
SITE = "https://lakelogic.github.io/open-lakehouse-contract"
SCHEMA_V1 = f"{SITE}/schema/v1/open-lakehouse-contract.schema.json"
SCHEMA_LATEST = f"{SITE}/schema/latest/open-lakehouse-contract.schema.json"
LINT_RULES = "https://lakelogic.github.io/LakeLogic/contracts/lint_rules.html"
EXAMPLE = ROOT / "examples" / "orders.olc.yaml"
FULL_EXAMPLE = ROOT / "examples" / "full.olc.yaml"
OUT = DOCS / "llms.txt"
OUT_FULL = DOCS / "llms-full.txt"


def nav_pages() -> list[tuple[str, str, str]]:
    """``(section, title, path)`` for every page in mkdocs.yml's nav, in order.

    Read with a regex rather than a YAML parser: mkdocs.yml carries ``!!python/name`` tags a
    safe loader refuses.
    """
    text = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    nav = text[text.index("\nnav:") : text.index("\nplugins:")]
    pages, section = [], "Start here"
    for line in nav.splitlines():
        m = re.match(r"^  - ([^:]+):\s*$", line)
        if m:
            section = m.group(1).strip()
            continue
        m = re.match(r"^  - (.+?):\s+(\S+\.md)\s*$", line)  # a top-level page, outside any section
        if m:
            pages.append(("Start here", m.group(1).strip(), m.group(2).strip()))
            continue
        m = re.match(r"^\s+- (.+?):\s+(\S+\.md)\s*$", line)
        if m:
            pages.append((section, m.group(1).strip(), m.group(2).strip()))
    return pages


def page_url(path: str) -> str:
    return f"{SITE}/{path[:-3]}.html"  # use_directory_urls: false


SKELETON = """version: 1.0.0                      # the contract's own version
info:
  title: Trips
  table_name: silver_trips
  target_layer: silver               # bronze | silver | gold
source:
  type: landing                      # see source.type below
  path: landing/trips/
  format: parquet
  partition:
    format: "y_%Y/m_%m/d_%d"         # folder layout, strftime tokens
model:
  fields:
    - { name: trip_id, type: string, required: true }
    - { name: rider_email, type: string, pii: true, masking: hash }
    - { name: fare, type: float }
    - { name: updated_at, type: timestamp }
    - { name: is_deleted, type: boolean }
primary_key: [trip_id]               # TOP LEVEL: never inside materialization
transformations:
  - phase: pre
    deduplicate: { on: [trip_id], sort_by: [updated_at], order: desc }
quality:
  row_rules:
    - not_null: trip_id
    - range: { field: fare, min: 0, max: 1000 }
  dataset_rules:
    - unique: trip_id
materialization:
  strategy: merge                    # append | overwrite | merge | scd2
  format: delta
  soft_delete_column: is_deleted     # how source deletes arrive (lint DEL-001)
service_levels:
  freshness: 24h
schedule: "0 6 * * *"                # TOP LEVEL cron: not under service_levels
"""


MISTAKES = [
    "In a one-line field (`- { name: x, description: ... }`) a comma ends the value: quote any "
    "text that has a comma or a colon (`description: \"Kept, not removed\"`), or the rest becomes an "
    "unknown key.",
    "`primary_key` goes at the TOP LEVEL of the contract, never inside `materialization`.",
    "A date-partitioned landing folder is `source.partition.format` (e.g. `\"y_%Y/m_%m/d_%d\"`), not "
    "`source.partition_pattern`.",
    "Deduplicate with `deduplicate: {on: [...], sort_by: [...], order: desc}`. The older "
    "`deduplicate_by_latest` takes `key_columns` and `timestamp_column` only; prefer `deduplicate`.",
    "`deduplicate.on` is the business key ONLY. Never put the `sort_by` column in it: "
    "`on: [customer_id, updated_at]` makes every row its own group, so nothing is deduplicated "
    "(lint KEY-002). Write `on: [customer_id]`, `sort_by: [updated_at]`. This holds for scd2 too.",
    "`schedule` is a top-level cron string; `service_levels` holds `freshness` / `row_count`.",
    "EVERY silver or gold table loaded with `merge` or `scd2` must say how source deletes arrive: add "
    "a boolean field (e.g. `is_deleted`) and `materialization.soft_delete_column: is_deleted`. "
    "Without it, rows deleted at the source stay in the table forever (lint DEL-001). Do this even "
    "when the request does not mention deletes.",
    "`trim`, `lower` and `upper` take an object with `fields`, not a bare list: "
    "`trim: {fields: [full_name, email]}`, `lower: {fields: [email]}`.",
    "`derive` takes `field` (the column it writes) and `sql`: `derive: {field: total, sql: amount + fee}`. "
    "Not `name`.",
    "`rollup.aggregations` is a MAPPING of output column to expression, not a list: "
    "`rollup: {group_by: [city, day], aggregations: {revenue: SUM(fare), trips: COUNT(*)}}`.",
    "There is no `apiVersion`, `kind`, `spec`, `schema` or `servers` key: OLC is not ODCS or a "
    "Kubernetes resource. The top level is exactly the keys in the skeleton above.",
]


def _model_facts() -> list[str]:
    required = [k for k, f in OLCContractV1.model_fields.items() if f.is_required()]
    ops = [k for k in Transformation.model_fields if k != "phase"]
    return [
        f"- Required top-level keys: {', '.join(f'`{k}`' for k in required)}. Unknown keys are refused: "
        "the schema is closed, so a misspelled key fails validation instead of being ignored.",
        "- `version` is the contract's own version (e.g. `1.0.0`). `info` carries at least `title`; "
        "`info.table_name` names the output table.",
        "- `model.fields` is a list of `{name, type}` (plus optional `required`, `pii`, `sensitive`, "
        "`masking`, `description`, `rules`).",
        f"- `source.type` is one of: {', '.join(f'`{t}`' for t in SOURCE_TYPES)}.",
        f"- `source.format` is one of: {', '.join(f'`{f}`' for f in SOURCE_FORMATS)}.",
        f"- A transformation is a list item with exactly one operation: {', '.join(f'`{o}`' for o in ops)}; "
        "optional `phase: pre|post` (see Execution Order).",
        "- `deduplicate` needs `on` (the key) AND `sort_by` (a column that DIFFERS between duplicates, "
        "normally `updated_at`) with `order: desc`; without an ordering it is refused.",
        "- `materialization.strategy: merge|scd2` needs `primary_key`; `scd2` also needs "
        "`materialization.scd2.track_columns`.",
        "- Quality: `quality.row_rules` (per row; a failing row is quarantined) and "
        "`quality.dataset_rules` (whole table). Shorthands: `not_null`, `accepted_values`, `range`, "
        "`regex_match`, `unique`, `null_ratio`, `row_count_between`, or `{name, sql}`.",
        "- Personal data: tag `pii: true` and give a `masking` strategy (`hash|redact|partial|nullify`).",
        "- `schema_policy` (`evolution`, `unknown_fields`) may be stated at the top level or under `server`.",
        "- Iceberg tables are written through a catalog (`table:<catalog>.<namespace>.<table>`), never a path.",
        "- YAML: `on` is a field name. Parsers that follow YAML 1.1 read a bare `on:` as `true`; OLC "
        "tools read it as the string `on`.",
    ]


def render_llms() -> str:
    pages = nav_pages()
    by_section: dict[str, list[tuple[str, str]]] = {}
    for section, title, path in pages:
        by_section.setdefault(section, []).append((title, path))

    out = [
        "# Open Lakehouse Contract (OLC)",
        "",
        "> OLC is an open standard for data contracts that both DESCRIBE and EXECUTE a data product: "
        "schema, quality rules, personal-data handling, transformations, materialization, lineage and "
        "service levels in one YAML file, portable across engines (Spark, DuckDB, Polars) and platforms "
        "(Databricks, Snowflake, Microsoft Fabric, BigQuery, AWS, MotherDuck).",
        "",
        "Before you hand a contract to anyone, check it. `olc validate <file>` checks it against the "
        "schema; `lakelogic validate <file>` checks the runtime can enforce it; `lakelogic lint <file>` "
        "reviews it for governance gaps.",
        "",
        "## Writing a contract that validates first time",
        "",
        "Every top-level key in its place (all optional except `version`, `info` and `model`):",
        "",
        "```yaml",
        SKELETON.rstrip(),
        "```",
        "",
        *_model_facts(),
        "",
        "## Common mistakes",
        "",
        "Found by running LLMs against this file; each one fails validation or lint:",
        "",
        *[f"- {m}" for m in MISTAKES],
        "",
        "## Schema",
        "",
        f"- [JSON Schema, v1]({SCHEMA_V1}): pin this version.",
        f"- [JSON Schema, latest]({SCHEMA_LATEST}): the current version.",
        "",
        "## Lint rules",
        "",
        f"- [Lint rule catalogue]({LINT_RULES}): every `lakelogic lint` rule with why it matters, a "
        "failing contract and the fix.",
        "",
    ]
    for section in ("Start here", "Reference", "Concepts", "Providers"):
        entries = by_section.get(section, [])
        if not entries:
            continue
        out += [f"## {section}", ""]
        out += [f"- [{title}]({page_url(path)})" for title, path in entries]
        out.append("")
    out += [
        "## Example",
        "",
        "A small, complete contract that validates (from `examples/orders.olc.yaml`):",
        "",
        "```yaml",
        EXAMPLE.read_text(encoding="utf-8").rstrip(),
        "```",
        "",
        "## Optional",
        "",
        f"- [llms-full.txt]({SITE}/llms-full.txt): every reference page and example in one file.",
    ]
    return "\n".join(out).rstrip() + "\n"


def render_llms_full() -> str:
    out = [
        "# Open Lakehouse Contract (OLC): full reference",
        "",
        f"Generated from the OLC docs ({SITE}). The summary and the rules for writing a contract that "
        f"validates first time are in {SITE}/llms.txt.",
        "",
    ]
    for section, title, path in nav_pages():
        if section == "Providers" or title in ("Overview", "Contributing"):
            continue
        body = (DOCS / path).read_text(encoding="utf-8").strip()
        out += ["", "=" * 80, f"# {section}: {title}", f"Source: {page_url(path)}", "=" * 80, "", body, ""]
    for example in (EXAMPLE, FULL_EXAMPLE):
        out += ["", "=" * 80, f"# Example: {example.name}", "=" * 80, "", "```yaml",
                example.read_text(encoding="utf-8").rstrip(), "```", ""]
    return "\n".join(out).rstrip() + "\n"


def main(argv: list[str]) -> int:
    targets = {OUT: render_llms(), OUT_FULL: render_llms_full()}
    if "--check" in argv:
        stale = [p for p, text in targets.items() if (p.read_text(encoding="utf-8") if p.exists() else "") != text]
        for p in stale:
            print(f"{p.relative_to(ROOT)} is stale: run python scripts/generate_llms.py")
        if not stale:
            print("llms.txt and llms-full.txt are up to date")
        return 1 if stale else 0
    for path, text in targets.items():
        path.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {path.relative_to(ROOT)} ({len(text):,} characters)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
