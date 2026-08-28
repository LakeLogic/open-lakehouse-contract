"""The ``service_levels.completeness`` commitment — parsing and strictness.

``completeness`` is the fraction of EXPECTED partitions that must arrive for a
partitioned source, where "expected" means the intervals a seasonal baseline says
always deliver — not every interval enumerated in the window. That denominator is
the whole point of the field, so it is asserted here as documentation the test
suite enforces: a source with genuinely idle intervals must be able to declare
``1.0`` and mean it.

It is typed exactly like ``availability`` (scalar shorthand or a full
:class:`ServiceLevelObjective`), and reuses ``ServiceLevelObjective`` rather than
introducing a fourth SLO shape.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from olc.models import OLCContractV1, load_strict
from olc.models._nested import ServiceLevel, ServiceLevelObjective

ROOT = Path(__file__).resolve().parents[1]


def _contract(**service_levels) -> dict:
    """A minimal valid contract, optionally carrying a ``service_levels`` block."""
    doc: dict = {
        "version": "1.0.0",
        "info": {"title": "Test", "table_name": "test"},
        "model": {"fields": [{"name": "id", "type": "integer"}]},
    }
    if service_levels:
        doc["service_levels"] = dict(service_levels)
    return doc


class CompletenessModelTests(unittest.TestCase):
    """The field parses in both spellings, and stays optional."""

    def test_scalar_form_parses(self) -> None:
        contract = load_strict(_contract(completeness=1.0))
        self.assertEqual(contract.service_levels.completeness, 1.0)

    def test_object_form_parses(self) -> None:
        """The SLO object form reuses ServiceLevelObjective — no new model class."""
        contract = load_strict(
            _contract(
                completeness={
                    "description": "Every hour that historically delivers must arrive.",
                    "threshold": 0.99,
                }
            )
        )
        slo = contract.service_levels.completeness
        self.assertIsInstance(slo, ServiceLevelObjective)
        self.assertEqual(slo.threshold, 0.99)
        self.assertEqual(
            slo.description, "Every hour that historically delivers must arrive."
        )

    def test_idle_intervals_can_declare_a_full_commitment(self) -> None:
        """1.0 is expressible and meaningful.

        The denominator is the always-delivers baseline, not raw enumeration, so a
        rideshare feed that is legitimately idle at 03:00 declares 1.0 rather than
        being forced down to 0.9 purely to stay quiet.
        """
        contract = load_strict(_contract(completeness=1.0))
        self.assertEqual(contract.service_levels.completeness, 1.0)

    def test_omitted_is_none_and_siblings_are_unchanged(self) -> None:
        contract = load_strict(
            _contract(freshness="24h", availability=99.5, row_count={"min_rows": 1})
        )
        levels = contract.service_levels
        self.assertIsNone(levels.completeness)
        self.assertEqual(levels.freshness, "24h")
        self.assertEqual(levels.availability, 99.5)
        self.assertEqual(levels.row_count.min_rows, 1)

    def test_absent_service_levels_block_still_valid(self) -> None:
        self.assertIsNone(load_strict(_contract()).service_levels)

    def test_completeness_is_declared_on_the_model(self) -> None:
        self.assertIn("completeness", ServiceLevel.model_fields)


class CompletenessStrictKeyTests(unittest.TestCase):
    """The strict path walks *declared* fields, so a new field is accepted
    automatically — asserted rather than assumed — while an unknown sibling is
    still refused."""

    def test_strict_path_accepts_the_new_key(self) -> None:
        # No exception == accepted by collect_unknown_nested_keys.
        load_strict(_contract(completeness=0.95))

    def test_unknown_sibling_is_still_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            load_strict(_contract(completeness=0.95, completenes=0.95))
        self.assertIn("service_levels.completenes", str(ctx.exception))

    def test_misspelled_key_alone_is_rejected(self) -> None:
        """Guards the failure mode the new field creates: a near-miss spelling must
        not be silently ignored, or a contract would claim a commitment it never made."""
        with self.assertRaises(ValueError) as ctx:
            load_strict(_contract(completeness_ratio=1.0))
        self.assertIn("service_levels.completeness_ratio", str(ctx.exception))


class CompletenessPublishedSchemaTests(unittest.TestCase):
    """A third party validating against the published schema alone gets the same
    guarantees — the schema is the artifact outside implementations consume."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(
            (ROOT / "schema" / "open-lakehouse-contract.schema.json").read_text(
                encoding="utf-8"
            )
        )
        cls.validator = Draft202012Validator(cls.schema)

    def _errors(self, doc: dict) -> list:
        return [e.message for e in self.validator.iter_errors(doc)]

    def test_schema_accepts_scalar_and_object_forms(self) -> None:
        self.assertEqual(self._errors(_contract(completeness=1.0)), [])
        self.assertEqual(
            self._errors(_contract(completeness={"threshold": 0.9})), []
        )

    def test_schema_rejects_an_unknown_sibling(self) -> None:
        self.assertTrue(self._errors(_contract(completeness=1.0, bogus=1.0)))

    def test_schema_documents_the_denominator(self) -> None:
        """The denominator rule is the ambiguous part of the field; if it is not in
        the published schema, an outside implementer cannot know what to measure."""
        description = self.schema["$defs"]["ServiceLevel"]["properties"][
            "completeness"
        ]["description"]
        self.assertIn("EXPECTED", description)
        self.assertIn("NOT every interval enumerated", description)

    def test_schema_reuses_the_service_level_objective(self) -> None:
        refs = [
            branch.get("$ref")
            for branch in self.schema["$defs"]["ServiceLevel"]["properties"][
                "completeness"
            ]["anyOf"]
        ]
        self.assertIn("#/$defs/ServiceLevelObjective", refs)


class CompletenessIsNotMonitorTuningTests(unittest.TestCase):
    """Lookback / minimum history / flake tolerance are stateful and temporal, so
    they live in SaaS monitor config, following the precedent volume drop states.
    Their absence from OLC is a deliberate design property worth guarding."""

    FORBIDDEN = (
        "lookback_days",
        "min_history",
        "min_missing_to_fire",
        "max_historical_absences",
        "grain",
    )

    def test_no_temporal_knobs_leaked_into_service_levels(self) -> None:
        for name in self.FORBIDDEN:
            self.assertNotIn(name, ServiceLevel.model_fields, name)

    def test_temporal_knobs_are_rejected_by_the_strict_path(self) -> None:
        for name in self.FORBIDDEN:
            with self.assertRaises(ValueError, msg=name):
                load_strict(_contract(completeness=1.0, **{name: 7}))

    def test_grain_still_comes_from_the_partition_format(self) -> None:
        """No new grain field: an `%H` token in source.partition.format is the grain."""
        doc = _contract(completeness=1.0)
        doc["source"] = {
            "type": "landing",
            "path": "{landing_root}/events",
            "partition": {"format": "y_%Y/m_%m/d_%d/h_%H", "lookback_days": 3},
        }
        contract = OLCContractV1.model_validate(doc)
        self.assertIn("%H", contract.source.partition.format)


if __name__ == "__main__":
    unittest.main()
