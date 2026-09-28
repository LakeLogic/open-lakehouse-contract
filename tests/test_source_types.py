"""`source.type` is a closed set, defined once in olc.models._nested.

The reference framework imports SOURCE_TYPES rather than keeping its own list; its
dispatch is tested against it there. Here: the model rejects an unknown kind with a
message that names the allowed ones, and the published schema carries the same
enum with one description per value.
"""

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from pydantic import ValidationError

from olc.models._nested import SOURCE_TYPE_DESCRIPTIONS, SOURCE_TYPES, SourceConfig

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schema" / "open-lakehouse-contract.schema.json").read_text(encoding="utf-8"))


class SourceTypeTests(unittest.TestCase):
    def test_the_set_is_exactly_the_eight_the_engine_reads(self) -> None:
        self.assertEqual(
            set(SOURCE_TYPES),
            {"landing", "stream", "table", "delta", "iceberg", "database", "dlt", "sftp"},
        )

    def test_every_value_loads(self) -> None:
        for kind in SOURCE_TYPES:
            self.assertEqual(SourceConfig(type=kind).type, kind)

    def test_unknown_values_fail_and_name_the_allowed_ones(self) -> None:
        for bad in ("api", "sql", "file", "parquet", "local", "event", "DLT"):
            with self.assertRaises(ValidationError) as ctx:
                SourceConfig(type=bad)
            message = str(ctx.exception)
            for kind in SOURCE_TYPES:
                self.assertIn(f"'{kind}'", message)

    def test_schema_enum_matches_the_model_with_a_description_per_value(self) -> None:
        prop = SCHEMA["$defs"]["SourceConfig"]["properties"]["type"]
        self.assertEqual(prop["enum"], list(SOURCE_TYPES))
        self.assertEqual(prop["enumDescriptions"], [SOURCE_TYPE_DESCRIPTIONS[k] for k in SOURCE_TYPES])
        for kind in SOURCE_TYPES:
            self.assertIn(f"`{kind}`", prop["description"])

    def test_schema_rejects_an_unknown_source_type(self) -> None:
        validator = Draft202012Validator(SCHEMA)
        doc = {"version": "1.0.0", "info": {"title": "t"}, "model": {"fields": []}}
        ok = dict(doc, source={"type": "dlt"})
        bad = dict(doc, source={"type": "api"})
        def type_errors(doc):
            # `source` is optional, so a bad kind surfaces inside the anyOf's context.
            return [
                c.message
                for e in validator.iter_errors(doc)
                if list(e.path) == ["source"]
                for c in e.context
                if list(c.path) == ["type"]
            ]

        self.assertEqual(type_errors(ok), [])
        self.assertEqual(len(type_errors(bad)), 1)
        self.assertIn("'api' is not one of", type_errors(bad)[0])


if __name__ == "__main__":
    unittest.main()
