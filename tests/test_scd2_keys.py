"""The `materialization.scd2` block has a declared key vocabulary.

`scd2` stays typed `Dict[str, Any]` (the reference runtime calls `.get()` on it),
so the vocabulary is declared as data in `olc.models._nested` and checked by the
strict OLC v1 path only. These tests pin both halves of that bargain:

  * strict rejects a misspelled key and NAMES it, and
  * the lenient runtime model still parses the very same contract.

The second half is the backward-compatibility guard: contracts already in the wild
must keep loading.
"""

from __future__ import annotations

import unittest

from olc.models import load_strict
from olc.models._nested import SCD2_KNOWN_KEYS, SCD2_UNKNOWN_MEMBER_KNOWN_KEYS

try:  # the lenient runtime model — optional, only present with the reference runtime
    from lakelogic.core.models import DataContract
except Exception as exc:  # pragma: no cover - environment without the runtime
    DataContract = None
    _RUNTIME_ERROR = exc
else:
    _RUNTIME_ERROR = None


def _contract(scd2: dict) -> dict:
    return {
        "version": "1.0.0",
        "info": {"title": "dim_customer"},
        "model": {"fields": [{"name": "customer_id", "type": "string"}]},
        "primary_key": ["customer_id"],
        "materialization": {"strategy": "scd2", "scd2": scd2},
    }


# One value per declared key, typed the way the runtime expects to read it.
_EVERY_KNOWN_KEY = {
    "surrogate_key": "_sk",
    "surrogate_key_strategy": "hash",
    "effective_from_field": "effective_from",
    "effective_to_field": "effective_to",
    "current_flag_field": "is_current",
    "version_column": "_version",
    "change_reason_column": "_change_reason",
    "track_columns": ["tier"],
    "timestamp_field": "updated_at",
    "change_date_field": "updated_at",
    "end_date_default": "9999-12-31",
    "effective_to_default": "9999-12-31",
    "start_date_default": "1900-01-01",
    "effective_from_default": "1900-01-01",
    "default_effective_from": "2024-01-01T00:00:00+00:00",
    "merge_dedup_guard": True,
    "unknown_member": {
        "enabled": True,
        "surrogate_key_value": "-1",
        "default_values": {"customer_id": "_UNKNOWN"},
    },
}


class Scd2VocabularyTests(unittest.TestCase):
    def test_declared_vocabulary_matches_the_fixture(self) -> None:
        """The fixture below must cover the vocabulary, or the parse test is hollow."""
        self.assertEqual(set(_EVERY_KNOWN_KEY), set(SCD2_KNOWN_KEYS))
        self.assertEqual(
            set(_EVERY_KNOWN_KEY["unknown_member"]),
            set(SCD2_UNKNOWN_MEMBER_KNOWN_KEYS),
        )

    def test_no_scd2_key_is_required(self) -> None:
        load_strict(_contract({}))


class Scd2StrictPathTests(unittest.TestCase):
    def test_every_known_key_parses_strict(self) -> None:
        contract = load_strict(_contract(_EVERY_KNOWN_KEY))
        self.assertEqual(contract.materialization.scd2, _EVERY_KNOWN_KEY)

    def test_typo_is_rejected_and_named(self) -> None:
        with self.assertRaises(Exception) as caught:
            load_strict(_contract({"track_column": ["tier"]}))
        message = str(caught.exception)
        self.assertIn("materialization.scd2.track_column", message)
        # …and points at the spelling that was meant.
        self.assertIn("did you mean 'track_columns'", message)

    def test_unknown_member_typo_is_rejected_and_named(self) -> None:
        with self.assertRaises(Exception) as caught:
            load_strict(_contract({"unknown_member": {"enabld": True}}))
        message = str(caught.exception)
        self.assertIn("materialization.scd2.unknown_member.enabld", message)
        self.assertIn("did you mean 'enabled'", message)

    def test_invented_key_is_rejected_even_without_a_near_match(self) -> None:
        with self.assertRaises(Exception) as caught:
            load_strict(_contract({"business_key": ["customer_id"]}))
        self.assertIn("materialization.scd2.business_key", str(caught.exception))

    def test_other_free_form_bags_stay_open(self) -> None:
        """Only registered bags are checked — `compliance` et al. must stay opaque."""
        document = _contract(_EVERY_KNOWN_KEY)
        document["compliance"] = {"whatever_we_like": {"nested": True}}
        document["metadata"] = {"anything": 1}
        load_strict(document)


@unittest.skipIf(DataContract is None, f"reference runtime unavailable: {_RUNTIME_ERROR}")
class Scd2LenientPathTests(unittest.TestCase):
    """Backward compatibility: the lenient runtime model must not get stricter."""

    def test_every_known_key_parses_lenient(self) -> None:
        contract = DataContract(**_contract(_EVERY_KNOWN_KEY))
        self.assertEqual(contract.materialization.scd2, _EVERY_KNOWN_KEY)

    def test_typo_still_parses_lenient(self) -> None:
        contract = DataContract(**_contract({"track_column": ["tier"]}))
        self.assertEqual(contract.materialization.scd2, {"track_column": ["tier"]})

    def test_invented_key_still_parses_lenient(self) -> None:
        contract = DataContract(**_contract({"business_key": ["customer_id"]}))
        self.assertEqual(
            contract.materialization.scd2, {"business_key": ["customer_id"]}
        )


if __name__ == "__main__":
    unittest.main()
