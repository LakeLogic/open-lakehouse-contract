"""The `materialization.scd1` block is a declared field with a declared key vocabulary.

The reference runtime writes a type-1 dimension's surrogate key from `materialization.scd1`
under `strategy: merge`, and `Materialization._MAT_KNOWN_KEYS` already listed `scd1` — so the
LENIENT runtime model accepted it. But the canonical STRICT path walks declared fields, and
`scd1` was not one, so a contract using the runtime's own feature was rejected by the standard
meant to describe it ("unknown key(s) not permitted in canonical OLC contract:
materialization.scd1").

Like `scd2`, the block stays typed `Dict[str, Any]` (the runtime calls `.get()` on it) and its
vocabulary is checked by the strict path only. These tests pin:

  * the strict path ACCEPTS `scd1` — the bug this closes;
  * the strict path rejects a misspelled key inside it and names it; and
  * the lenient runtime model still parses the same contract (backward compatibility).
"""

from __future__ import annotations

import unittest

from olc.models import load_strict
from olc.models._nested import (
    SCD1_KNOWN_KEYS,
    SCD1_UNKNOWN_MEMBER_KNOWN_KEYS,
    SCD2_UNKNOWN_MEMBER_KNOWN_KEYS,
)

try:  # the lenient runtime model — optional, only present with the reference runtime
    from lakelogic.core.models import DataContract
except Exception as exc:  # pragma: no cover - environment without the runtime
    DataContract = None
    _RUNTIME_ERROR = exc
else:
    _RUNTIME_ERROR = None


def _contract(scd1: dict) -> dict:
    return {
        "version": "1.0.0",
        "info": {"title": "dim_city"},
        "model": {
            "fields": [
                {"name": "city_sk", "type": "string"},
                {"name": "city_code", "type": "string"},
            ]
        },
        "primary_key": ["city_code"],
        "natural_key": ["city_code"],
        "materialization": {"strategy": "merge", "scd1": scd1},
    }


# One value per declared key, typed the way the runtime reads it.
_EVERY_KNOWN_KEY = {
    "surrogate_key": "city_sk",
    "surrogate_key_strategy": "hash",
    "unknown_member": {
        "enabled": True,
        "surrogate_key_value": "-1",
        "default_values": {"city_code": "_UNKNOWN"},
    },
}


class Scd1VocabularyTests(unittest.TestCase):
    def test_declared_vocabulary_matches_the_fixture(self) -> None:
        """The fixture must cover the vocabulary, or the parse test is hollow."""
        self.assertEqual(set(_EVERY_KNOWN_KEY), set(SCD1_KNOWN_KEYS))
        self.assertEqual(
            set(_EVERY_KNOWN_KEY["unknown_member"]),
            set(SCD1_UNKNOWN_MEMBER_KNOWN_KEYS),
        )

    def test_the_unknown_member_reads_the_same_keys_as_scd2s(self) -> None:
        """The runtime injects both through one routine, so the vocabularies cannot drift."""
        self.assertEqual(SCD1_UNKNOWN_MEMBER_KNOWN_KEYS, SCD2_UNKNOWN_MEMBER_KNOWN_KEYS)

    def test_no_scd1_key_is_required(self) -> None:
        load_strict(_contract({}))


class Scd1StrictPathTests(unittest.TestCase):
    def test_the_strict_path_ACCEPTS_scd1(self) -> None:
        """THE BUG. This raised "unknown key(s) not permitted: materialization.scd1"."""
        contract = load_strict(_contract(_EVERY_KNOWN_KEY))
        self.assertEqual(contract.materialization.scd1, _EVERY_KNOWN_KEY)

    def test_typo_is_rejected_and_named(self) -> None:
        with self.assertRaises(Exception) as caught:
            load_strict(_contract({"surogate_key": "city_sk"}))
        message = str(caught.exception)
        self.assertIn("materialization.scd1.surogate_key", message)
        self.assertIn("did you mean 'surrogate_key'", message)

    def test_unknown_member_typo_is_rejected_and_named(self) -> None:
        with self.assertRaises(Exception) as caught:
            load_strict(_contract({"unknown_member": {"surrogate_key_valu": "-1"}}))
        message = str(caught.exception)
        self.assertIn("materialization.scd1.unknown_member.surrogate_key_valu", message)
        self.assertIn("did you mean 'surrogate_key_value'", message)

    def test_an_scd2_only_key_is_rejected_in_scd1(self) -> None:
        """A type-1 dimension keeps no history. `track_columns` there is not a harmless extra —
        it signals a contract that thinks it is SCD2 and will not get versions."""
        with self.assertRaises(Exception) as caught:
            load_strict(
                _contract({"surrogate_key": "city_sk", "track_columns": ["name"]})
            )
        self.assertIn("materialization.scd1.track_columns", str(caught.exception))

    def test_scd2_is_still_checked_independently(self) -> None:
        document = _contract(_EVERY_KNOWN_KEY)
        document["materialization"]["scd2"] = {"track_column": ["name"]}
        with self.assertRaises(Exception) as caught:
            load_strict(document)
        self.assertIn("materialization.scd2.track_column", str(caught.exception))


@unittest.skipIf(
    DataContract is None, f"reference runtime unavailable: {_RUNTIME_ERROR}"
)
class Scd1LenientPathTests(unittest.TestCase):
    """Backward compatibility: the lenient runtime model must not get stricter."""

    def test_every_known_key_parses_lenient(self) -> None:
        contract = DataContract(**_contract(_EVERY_KNOWN_KEY))
        self.assertEqual(contract.materialization.scd1, _EVERY_KNOWN_KEY)

    def test_typo_still_parses_lenient(self) -> None:
        contract = DataContract(**_contract({"surogate_key": "city_sk"}))
        self.assertEqual(contract.materialization.scd1, {"surogate_key": "city_sk"})


if __name__ == "__main__":
    unittest.main()
