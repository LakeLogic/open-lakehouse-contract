"""Contract YAML means the same thing to every reader.

YAML 1.1 resolves `on`, `off`, `yes`, `no` to booleans; PyYAML implements 1.1. So
`deduplicate: {on: [trip_id]}` — the documented way to declare dedup columns — became
`{True: ['trip_id']}` under `yaml.safe_load`.

The reference runtime already worked around it in a private CLI loader, so the engine
deduplicated correctly while every other reader (validators, diffs, revision readers)
silently lost the column list and reported a contract that does not exist. One file, two
meanings, decided by which import you happened to use.
"""
from __future__ import annotations

import yaml

from olc.yaml_compat import ContractYamlLoader, safe_load

DEDUP = "deduplicate:\n  on: [trip_id]\n  sort_by: [dropoff_at]\n"


class TestBooleanWordsStayStrings:
    def test_on_is_a_column_list_not_true(self):
        assert safe_load(DEDUP)["deduplicate"]["on"] == ["trip_id"]

    def test_stdlib_still_gets_it_wrong(self):
        # Pinning WHY this module exists. If PyYAML ever changes, this fails and the
        # workaround can be reconsidered rather than carried forever out of habit.
        assert True in yaml.safe_load(DEDUP)["deduplicate"]

    def test_the_other_yaml_1_1_words_survive_too(self):
        parsed = safe_load("a: yes\nb: no\nc: off\nd: on\n")
        assert parsed == {"a": "yes", "b": "no", "c": "off", "d": "on"}

    def test_real_booleans_are_still_booleans(self):
        # The point is not "no booleans" — `enabled: true` must keep working.
        parsed = safe_load("a: true\nb: false\nc: True\nd: FALSE\n")
        assert parsed == {"a": True, "b": False, "c": True, "d": False}


class TestNoActionAtADistance:
    def test_pyyaml_own_loader_is_untouched(self):
        # The resolver map is inherited, so editing it in place would reconfigure
        # PyYAML process-wide — a fix that breaks unrelated code is not a fix.
        assert yaml.safe_load("x: on") == {"x": True}

    def test_the_loader_is_a_safe_loader(self):
        # Security posture is unchanged: no arbitrary object construction.
        assert issubclass(ContractYamlLoader, yaml.SafeLoader)
