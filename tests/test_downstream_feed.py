"""A ``downstream`` consumer of ``type: feed`` — data sent outside the platform (2026-11-26).

Declared, never observed: a feed is as complete as its contract says. The fields that make
it a feed (destination, format, delivery, path) must pass the strict contract check and the
published JSON schema, or nobody can write one without a validation error.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from olc.models import load_strict

ROOT = Path(__file__).resolve().parents[1]

FEED = {
    "type": "feed",
    "name": "Driver payouts to Sage",
    "destination": "sage",
    "format": "csv",
    "delivery": "sftp",
    "path": "/outbound/payouts/",
    "refresh": "daily 02:00 UTC",
    "owner": "Finance Engineering",
    "columns_used": ["driver_id", "payout_amount"],
}


def _contract(downstream):
    return {
        "version": "1.0.0",
        "info": {
            "title": "Driver payouts",
            "table_name": "gold_rideflow_driver_payouts",
        },
        "model": {"fields": [{"name": "driver_id", "type": "string"}]},
        "downstream": downstream,
    }


class DownstreamFeedTests(unittest.TestCase):
    def test_a_feed_passes_the_strict_check(self) -> None:
        feed = load_strict(_contract([FEED])).downstream[0]
        self.assertEqual(
            (feed.destination, feed.format, feed.delivery), ("sage", "csv", "sftp")
        )
        self.assertEqual(feed.columns_used, ["driver_id", "payout_amount"])

    def test_a_feed_passes_the_published_schema(self) -> None:
        schema = json.loads(
            (ROOT / "schema" / "open-lakehouse-contract.schema.json").read_text(
                encoding="utf-8"
            )
        )
        errors = list(Draft202012Validator(schema).iter_errors(_contract([FEED])))
        self.assertEqual(errors, [])

    def test_existing_consumers_are_unchanged(self) -> None:
        report = {"type": "report", "name": "Weekly Sales", "platform": "power_bi"}
        self.assertIsNone(load_strict(_contract([report])).downstream[0].destination)
