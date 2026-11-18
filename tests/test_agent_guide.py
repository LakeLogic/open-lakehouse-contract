"""The agent guide is complete and short (owner, 2026-11-18).

"Full capabilities across the board should be easy to find by any agent": every top-level
contract key has an index entry an agent can find, and the standing-context block stays
short enough to scan - the field tables live in olc-reference.md / `olc reference`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from generate_reference import CAPABILITIES, SCHEMA_PATH, TASKS, build_guide  # noqa: E402

SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_every_top_level_key_has_an_index_entry():
    missing = set(SCHEMA["properties"]) - set(CAPABILITIES)
    assert not missing, f"add these to CAPABILITIES in scripts/generate_reference.py: {sorted(missing)}"
    assert not set(CAPABILITIES) - set(SCHEMA["properties"]), "CAPABILITIES names a key the schema dropped"


def test_task_rows_only_name_keys_that_exist():
    import re

    known = set(SCHEMA["properties"]) | {k for d in SCHEMA["$defs"].values() for k in d.get("properties", {})}
    for task, keys in TASKS:
        for key in re.findall(r"`([a-z]\w*)[.:]", keys):   # `_domain.yaml` is a file, not a key
            assert key in known, f"{task}: `{key}` is not a key the schema declares"


def test_guide_is_scannable():
    guide = build_guide(SCHEMA)
    assert len(guide.splitlines()) < 300
    assert "olc reference" in guide and "lakelogic agent-guide" in guide


def test_cli_prints_the_guide_and_one_section(capsys):
    from olc.cli import main

    assert main(["reference", "Quarantine"]) == 0
    assert capsys.readouterr().out.startswith("## Quarantine")
    assert main(["reference", "Top", "level"]) == 0
    assert main(["guide"]) == 0
    assert "## How do I" in capsys.readouterr().out
