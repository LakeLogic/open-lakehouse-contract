"""``compliance.retention``: a contract's own retention period (2026-10-19).

It overrides the domain's per-layer period for one contract. ``compliance`` itself stays an
open map, so existing entries (``erasure`` …) keep validating; only ``retention`` is typed.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from olc.models import load_strict

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schema" / "open-lakehouse-contract.schema.json").read_text(encoding="utf-8"))


def contract(compliance: dict) -> dict:
    return {
        "version": "1.0.0",
        "info": {"title": "Driver profiles", "table_name": "silver_rideflow_driver_profiles"},
        "model": {"fields": [{"name": "driver_id", "type": "string"}, {"name": "signup_date", "type": "date"}]},
        "compliance": compliance,
    }


class TestModel(unittest.TestCase):
    def test_a_full_retention_block_validates(self) -> None:
        c = load_strict(contract({"retention": {
            "period": "P6Y", "column": "signup_date", "starts": "record_created",
            "basis": "Tax: 6 years from signup"}}))
        self.assertEqual(c.compliance["retention"]["period"], "P6Y")

    def test_the_period_alone_is_enough(self) -> None:
        for period in ("P90D", "P6Y", "P1Y6M", "P2W", "PT12H"):
            load_strict(contract({"retention": {"period": period}}))

    def test_a_period_that_is_not_a_duration_is_refused(self) -> None:
        for bad in ("6 years", "P", "PT", "P6YT", "6", "d400"):
            with self.assertRaises(ValueError, msg=bad) as ctx:
                load_strict(contract({"retention": {"period": bad}}))
            self.assertIn("compliance.retention", str(ctx.exception))

    def test_the_documented_short_form_still_validates(self) -> None:
        """The docs have shown `{period: 400d, basis: legal}` since the block was free-form."""
        from olc.models.compliance import iso_period

        load_strict(contract({"retention": {"period": "400d", "basis": "legal"}}))
        self.assertEqual(iso_period("400d"), "P400D")
        self.assertEqual(iso_period("6y"), "P6Y")
        self.assertEqual(iso_period("P1Y6M"), "P1Y6M")

    def test_a_misspelled_key_is_refused_not_ignored(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            load_strict(contract({"retention": {"period": "P6Y", "colum": "signup_date"}}))
        self.assertIn("colum", str(ctx.exception))

    def test_starts_is_a_closed_vocabulary(self) -> None:
        with self.assertRaises(ValueError):
            load_strict(contract({"retention": {"period": "P6Y", "starts": "whenever"}}))

    def test_the_period_is_required(self) -> None:
        with self.assertRaises(ValueError):
            load_strict(contract({"retention": {"column": "signup_date"}}))

    def test_other_compliance_keys_still_validate(self) -> None:
        load_strict(contract({"erasure": {"strategy": "delete"}, "anything_else": 1}))
        load_strict(contract({}))


class TestSchema(unittest.TestCase):
    def test_retention_is_typed_and_closed_while_compliance_stays_open(self) -> None:
        compliance = SCHEMA["properties"]["compliance"]
        self.assertIs(compliance["additionalProperties"], True)
        self.assertIn("retention", compliance["properties"])
        retention = SCHEMA["$defs"]["ContractRetention"]
        self.assertIs(retention["additionalProperties"], False)
        self.assertEqual(retention["required"], ["period"])
        self.assertEqual(
            retention["properties"]["starts"]["anyOf"][0]["enum"],
            ["record_created", "relationship_ended", "custom"],
        )


if __name__ == "__main__":
    unittest.main()
