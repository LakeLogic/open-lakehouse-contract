"""The exact forms of the ``unique`` rule and where ``primary_key`` goes.

Agents writing contracts were unsure of both, and several wrong spellings passed validation
(``unique: {column: id}``, ``unique: {field: [a, b]}``) only to check nothing — or crash — at
run time. Each case is checked against BOTH the published JSON Schema and the strict model.
"""
from __future__ import annotations

import unittest

from jsonschema import Draft202012Validator

from olc.models import OLCContractV1
from olc.models._nested import DatasetRuleUnique
from olc.validate import errors_for, load_schema

BASE = {
    "version": "1.0.0",
    "info": {"title": "Orders", "version": "1.0.0"},
    "model": {"fields": [{"name": "order_id", "type": "integer"}, {"name": "line_no", "type": "integer"}]},
}


def _with(**extra):
    return {**BASE, **extra}


def _rules(*rules):
    return _with(quality={"dataset_rules": list(rules)})


class _Both(unittest.TestCase):
    validator = Draft202012Validator(load_schema("schema/open-lakehouse-contract.schema.json"))

    def assertAccepted(self, doc):
        self.assertEqual(errors_for(doc, self.validator), [])
        OLCContractV1.model_validate(doc)

    def assertRejected(self, doc):
        self.assertTrue(errors_for(doc, self.validator), "schema accepted it")
        with self.assertRaises(Exception):
            OLCContractV1.model_validate(doc)


class UniqueRuleForms(_Both):
    def test_the_documented_forms_are_accepted(self):
        for rule in (
            {"unique": "order_id"},
            {"unique": ["order_id", "line_no"]},
            {"unique": {"field": "order_id"}},
            {"unique": {"columns": ["order_id", "line_no"], "name": "pk_unique", "severity": "warning"}},
            {"unique": {"fields": ["order_id", "line_no"]}},
            {"name": "order_id_unique", "unique": "order_id", "severity": "warning", "description": "one row per order"},
        ):
            with self.subTest(rule=rule):
                self.assertAccepted(_rules(rule))

    def test_misspelt_or_ambiguous_mappings_are_rejected(self):
        for rule in (
            {"unique": {"column": "order_id"}},
            {"unique": {"field": ["order_id", "line_no"]}},
            {"unique": {"field": "order_id", "columns": ["line_no"]}},
            {"unique": {}},
            {"unique": "order_id", "colour": "red"},
        ):
            with self.subTest(rule=rule):
                self.assertRejected(_rules(rule))

    def test_unique_is_not_a_row_rule(self):
        self.assertRejected(_with(quality={"row_rules": [{"unique": "order_id"}]}))

    def test_columns_and_labels_read_the_same_whatever_the_form(self):
        self.assertEqual(DatasetRuleUnique(unique="a").columns(), ["a"])
        self.assertEqual(DatasetRuleUnique(unique=["a", "b"]).columns(), ["a", "b"])
        inner = DatasetRuleUnique(unique={"fields": ["a", "b"], "severity": "warning"})
        self.assertEqual((inner.columns(), inner.label("severity")), (["a", "b"], "warning"))
        beside = DatasetRuleUnique(unique={"field": "a", "name": "inner"}, name="outer")
        self.assertEqual(beside.label("name"), "outer")


class PrimaryKeyPlacement(_Both):
    def test_top_level_list_is_the_only_place(self):
        self.assertAccepted(_with(primary_key=["order_id", "line_no"]))

    def test_under_model_or_on_a_field_is_rejected(self):
        self.assertRejected(_with(model={**BASE["model"], "primary_key": ["order_id"]}))
        self.assertRejected(_with(model={"fields": [{"name": "order_id", "type": "integer", "primary_key": True}]}))
        self.assertRejected(_with(model={"fields": [{"name": "order_id", "type": "integer", "unique": True}]}))


if __name__ == "__main__":
    unittest.main()
