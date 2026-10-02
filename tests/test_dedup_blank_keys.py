"""`deduplicate.blank_keys` — what happens to rows whose dedup key is blank.

A blank key (ANY key column null) is never a duplicate of another blank key, so those
rows are never collapsed. `blank_keys` picks between quarantining them (default) and
keeping them. These tests pin the model default, the closed vocabulary, and that the
strict path and the published JSON Schema both accept the key.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from pydantic import ValidationError

from olc.models import load_strict
from olc.models._nested import TransformationDeduplicate

SCHEMA = Path(__file__).resolve().parents[1] / "schema" / "open-lakehouse-contract.schema.json"


def _contract(dedup: dict) -> dict:
    return {
        "version": "1.0.0",
        "info": {"title": "trips"},
        "model": {"fields": [{"name": "trip_id", "type": "string"}, {"name": "ts", "type": "string"}]},
        "transformations": [{"phase": "pre", "deduplicate": dedup}],
    }


class TestBlankKeysModel(unittest.TestCase):
    def test_default_is_quarantine(self):
        self.assertEqual(TransformationDeduplicate(on=["trip_id"], sort_by=["ts"]).blank_keys, "quarantine")

    def test_keep_accepted(self):
        self.assertEqual(
            TransformationDeduplicate(on=["trip_id"], sort_by=["ts"], blank_keys="keep").blank_keys, "keep"
        )

    def test_unknown_value_rejected(self):
        with self.assertRaises(ValidationError):
            TransformationDeduplicate(on=["trip_id"], sort_by=["ts"], blank_keys="drop")


class TestBlankKeysStrict(unittest.TestCase):
    def test_strict_accepts_both_values(self):
        for value in ("quarantine", "keep"):
            c = load_strict(_contract({"on": ["trip_id"], "sort_by": ["ts"], "blank_keys": value}))
            self.assertEqual(c.transformations[0].deduplicate.blank_keys, value)

    def test_strict_rejects_unknown_value(self):
        with self.assertRaises(Exception):
            load_strict(_contract({"on": ["trip_id"], "sort_by": ["ts"], "blank_keys": "drop"}))

    def test_json_schema_declares_enum_and_default(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        prop = schema["$defs"]["TransformationDeduplicate"]["properties"]["blank_keys"]
        self.assertEqual(prop["enum"], ["quarantine", "keep"])
        self.assertEqual(prop["default"], "quarantine")

    def test_json_schema_validates_contract(self):
        try:
            import jsonschema
        except ImportError:  # pragma: no cover
            self.skipTest("jsonschema not installed")
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        jsonschema.validate(_contract({"on": ["trip_id"], "sort_by": ["ts"], "blank_keys": "keep"}), schema)
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(_contract({"on": ["trip_id"], "sort_by": ["ts"], "blank_keys": "drop"}), schema)


if __name__ == "__main__":
    unittest.main()
