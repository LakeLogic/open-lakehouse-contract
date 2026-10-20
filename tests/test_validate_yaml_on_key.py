"""`on` is an OLC field name, not a boolean: olc validate must accept the documented form."""

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from olc.validate import load_contract_yaml, validate_file

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads(
    (ROOT / "schema" / "open-lakehouse-contract.schema.json").read_text(
        encoding="utf-8"
    )
)

CONTRACT = """version: 1.0.0
info: { title: Trips, table_name: trips }
model:
  fields:
    - { name: trip_id, type: string }
    - { name: updated_at, type: timestamp }
transformations:
  - deduplicate: { on: [trip_id], sort_by: [updated_at], order: desc }
"""


class OnIsAFieldName(unittest.TestCase):
    def test_on_stays_a_string_and_true_stays_a_boolean(self):
        doc = load_contract_yaml("a: { on: [x], flag: true, word: yes }")
        self.assertEqual(doc["a"], {"on": ["x"], "flag": True, "word": "yes"})

    def test_a_documented_deduplicate_validates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trips.olc.yaml"
            path.write_text(CONTRACT, encoding="utf-8")
            result = validate_file(path, Draft202012Validator(SCHEMA))
        self.assertTrue(result["valid"], result["errors"])

    def test_loading_does_not_change_safe_load_elsewhere(self):
        import yaml

        load_contract_yaml("x: on")
        self.assertIs(yaml.safe_load("x: on")["x"], True)


if __name__ == "__main__":
    unittest.main()
