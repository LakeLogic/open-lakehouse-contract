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


class DeduplicateSchemaTests(unittest.TestCase):
    """The PUBLISHED schema must enforce the dedup rules on its own.

    These held in pydantic already; the point is that a third-party implementation
    validating against the schema alone gets the same guarantees. Before `anyOf`,
    the alias pair (`on`/`by`) meant NEITHER appeared in `required`, so the schema
    accepted a deduplicate with no key at all — weaker than the model it publishes.
    """

    @classmethod
    def setUpClass(cls) -> None:
        full = json.loads(
            (ROOT / "schema" / "open-lakehouse-contract.schema.json").read_text(
                encoding="utf-8"
            )
        )
        sub = dict(full["$defs"]["TransformationDeduplicate"])
        sub["$defs"] = full["$defs"]
        cls.validator = Draft202012Validator(sub)

    def _errors(self, doc):
        return [e.message for e in self.validator.iter_errors(doc)]

    def test_both_key_spellings_are_accepted(self) -> None:
        self.assertEqual(self._errors({"on": ["id"], "sort_by": ["ts"]}), [])
        self.assertEqual(self._errors({"by": ["id"], "sort_by": ["ts"]}), [])

    def test_a_deduplicate_with_no_key_is_rejected(self) -> None:
        self.assertTrue(self._errors({"sort_by": ["ts"]}))

    def test_a_deduplicate_with_no_ordering_is_rejected(self) -> None:
        # The survivor would be engine-dependent; see conformance case OLC-T-002.
        self.assertTrue(self._errors({"on": ["id"]}))

    def test_bundled_schema_matches_the_published_one(self) -> None:
        """The bundled copy is what pip users validate against — it must not lag.

        The generator writes only `schema/`, so a regenerated schema ships stale
        unless the bundled copy is synced too.
        """
        published = (ROOT / "schema" / "open-lakehouse-contract.schema.json").read_text(
            encoding="utf-8"
        )
        bundled = (
            ROOT / "olc" / "_bundled" / "schema" / "open-lakehouse-contract.schema.json"
        ).read_text(encoding="utf-8")
        self.assertEqual(json.loads(published), json.loads(bundled))
