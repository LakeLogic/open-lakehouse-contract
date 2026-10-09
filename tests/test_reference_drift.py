"""Reference-drift gate: agent skills must describe the schema that ships.

``skills/olc-reference.md`` and the marked block in every standing-context skill file are
generated from the committed JSON Schema by ``scripts/generate_reference.py``. If the
schema changes and the generator is not re-run, agents keep writing the old format — so
this fails, the same way ``test_schema_drift`` fails for the schema itself. The release
script regenerates before it runs the tests.

It also proves the reference's own examples are valid OLC: a reference that teaches an
invalid shape is worse than none, because agents copy it.
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from generate_reference import (  # noqa: E402 - needs scripts/ on sys.path first
    CONTEXT_FILES,
    END,
    EXAMPLES,
    REFERENCE_PATH,
    SCHEMA_PATH,
    START,
    stale,
)


class ReferenceDriftTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_reference_and_skills_match_the_schema(self) -> None:
        bad = [str(p.relative_to(ROOT)) for p in stale(self.schema)]
        self.assertEqual(bad, [], "run: python scripts/generate_reference.py")

    def test_every_context_skill_carries_the_block(self) -> None:
        for rel in CONTEXT_FILES:
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn(START, text, rel)
            self.assertIn(END, text, rel)

    def test_reference_names_the_quality_rule_lists(self) -> None:
        text = REFERENCE_PATH.read_text(encoding="utf-8")
        self.assertIn("`row_rules`", text)
        self.assertIn("`dataset_rules`", text)

    def test_examples_are_valid_olc(self) -> None:
        try:
            import yaml

            from olc.models import OLCContractV1
        except Exception as exc:  # pragma: no cover - minimal checkout
            self.skipTest(f"model unavailable: {exc}")
        body = yaml.safe_load(
            re.search(r"```yaml\n(.*?)```", EXAMPLES, re.DOTALL).group(1)
        )
        doc = {
            "version": "1.0.0",
            "info": {"title": "Example", "owner": "data-eng"},
            "model": {
                "fields": [
                    {"name": n, "type": "string"}
                    for n in (
                        "trip_id",
                        "status",
                        "fare_amount",
                        "pickup_at",
                        "dropoff_at",
                        "duration_minutes",
                    )
                ]
            },
            **body,
        }
        OLCContractV1.model_validate(doc)


if __name__ == "__main__":
    unittest.main()
