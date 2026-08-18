from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


class PublishedSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(
            (ROOT / "schema" / "open-lakehouse-contract.schema.json").read_text(
                encoding="utf-8"
            )
        )

    def test_schema_is_valid_draft_2020_12(self) -> None:
        Draft202012Validator.check_schema(self.schema)

    def test_required_minimum_is_explicit(self) -> None:
        self.assertEqual(self.schema["required"], ["version", "info", "model"])

    def test_root_rejects_unknown_keys(self) -> None:
        self.assertFalse(self.schema["additionalProperties"])

    def test_typed_objects_are_closed(self) -> None:
        def visit(node: object) -> None:
            if isinstance(node, dict):
                if node.get("type") == "object" and isinstance(
                    node.get("properties"), dict
                ):
                    if node.get("title") != "Extensions":
                        self.assertFalse(
                            node.get("additionalProperties"),
                            node.get("title", "<object>"),
                        )
                for value in node.values():
                    visit(value)
            elif isinstance(node, list):
                for value in node:
                    visit(value)

        visit(self.schema)

    def test_extensions_are_namespaced(self) -> None:
        extensions = self.schema["properties"]["extensions"]
        self.assertTrue(extensions["additionalProperties"])
        self.assertIn("pattern", extensions["propertyNames"])


if __name__ == "__main__":
    unittest.main()
