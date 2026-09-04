"""Contract YAML means the same thing to every reader.

YAML 1.1 resolves `on`, `off`, `yes`, `no` to booleans; PyYAML implements 1.1. So
`deduplicate: {on: [trip_id]}` — the documented way to declare dedup columns — became
`{True: ['trip_id']}` under `yaml.safe_load`.

The reference runtime already worked around it in a private CLI loader, so the engine
deduplicated correctly while every other reader (validators, diffs, revision readers)
silently lost the column list and reported a contract that does not exist. One file, two
meanings, decided by which import you happened to use.

unittest, not pytest: `tests/` runs under `python -m unittest discover` with only
`pip install -e .[models]`, and pytest is installed for `conformance/` alone.
"""

from __future__ import annotations

import unittest

import yaml

from olc.yaml_compat import ContractYamlLoader, safe_load

DEDUP = "deduplicate:\n  on: [trip_id]\n  sort_by: [dropoff_at]\n"


class BooleanWordsStayStringsTests(unittest.TestCase):
    def test_on_is_a_column_list_not_true(self) -> None:
        self.assertEqual(safe_load(DEDUP)["deduplicate"]["on"], ["trip_id"])

    def test_stdlib_still_gets_it_wrong(self) -> None:
        # Pinning WHY this module exists. If PyYAML ever changes, this fails and the
        # workaround can be reconsidered rather than carried forever out of habit.
        self.assertIn(True, yaml.safe_load(DEDUP)["deduplicate"])

    def test_the_other_yaml_1_1_words_survive_too(self) -> None:
        self.assertEqual(
            safe_load("a: yes\nb: no\nc: off\nd: on\n"),
            {"a": "yes", "b": "no", "c": "off", "d": "on"},
        )

    def test_real_booleans_are_still_booleans(self) -> None:
        # The point is not "no booleans" — `enabled: true` must keep working.
        self.assertEqual(
            safe_load("a: true\nb: false\nc: True\nd: FALSE\n"),
            {"a": True, "b": False, "c": True, "d": False},
        )


class NoActionAtADistanceTests(unittest.TestCase):
    def test_pyyaml_own_loader_is_untouched(self) -> None:
        # The resolver map is inherited, so editing it in place would reconfigure PyYAML
        # process-wide — a fix that breaks unrelated code is not a fix.
        self.assertEqual(yaml.safe_load("x: on"), {"x": True})

    def test_the_loader_is_a_safe_loader(self) -> None:
        # Security posture unchanged: no arbitrary object construction.
        self.assertTrue(issubclass(ContractYamlLoader, yaml.SafeLoader))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
