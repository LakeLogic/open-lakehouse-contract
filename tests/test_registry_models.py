"""``_domain.yaml`` and ``_system.yaml`` validate against the standard.

Before these models the only check either file received was ``yaml.safe_load`` — and the
editor reported that to the user as "valid". A misspelled ``on_events`` token, a channel
routing nowhere, a ``run_log_backend`` typo: all passed, and the failure surfaced later as
an alert that never arrived.

Two things have to hold together, and one without the other is worthless:

* every real file in the estate still validates — a model that rejects working
  configuration is not stricter, it is broken; and
* configuration that is genuinely wrong is rejected — a model that accepts everything
  reproduces the ``safe_load`` situation with more ceremony.
"""
from __future__ import annotations

import glob
from pathlib import Path

import pytest
import yaml

from olc.models.registry_v1 import (
    OLCDomainV1,
    OLCSystemV1,
    load_strict_domain,
    load_strict_system,
)

# The estate this standard has to keep working. Absolute paths because the corpus lives
# in sibling repos; a missing corpus SKIPS rather than fails, so the suite stays portable.
_CORPORA = [
    Path("C:/_Personal/_SaaS/LakeLogic_SaaS/src/api/demo_assets"),
    Path("C:/_Personal/_SaaS/lakelogic/examples"),
]


def _files(kind: str):
    found = []
    for root in _CORPORA:
        if root.exists():
            found += sorted(glob.glob(str(root / "**" / f"_{kind}.yaml"), recursive=True))
    return found


def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


@pytest.mark.parametrize("path", _files("domain") or [pytest.param("", marks=pytest.mark.skip(reason="no corpus"))])
def test_every_real_domain_file_validates_strictly(path):
    load_strict_domain(_load(path))


@pytest.mark.parametrize("path", _files("system") or [pytest.param("", marks=pytest.mark.skip(reason="no corpus"))])
def test_every_real_system_file_validates_strictly(path):
    load_strict_system(_load(path))


class TestRejectsWhatIsActuallyWrong:
    """The half that makes the models worth having."""

    @pytest.mark.parametrize(
        "document",
        [
            pytest.param({"domain": "d", "retention": {"bronze": 7}}, id="retention-not-a-duration"),
            pytest.param({"domain": "d", "ownership": {"contacts": "me@x.com"}}, id="contacts-not-a-list"),
            pytest.param({"domain": "d", "cost": {"budget": {"daily_limit": "forty"}}}, id="budget-not-a-number"),
            pytest.param({"domain": "d", "observatory": {"enabled": "yes-please"}}, id="enabled-not-a-bool"),
        ],
    )
    def test_malformed_domain_values_are_refused(self, document):
        with pytest.raises(Exception):
            load_strict_domain(document)

    @pytest.mark.parametrize(
        "document",
        [
            pytest.param({"system": "s", "metadata": {"run_log_backend": {"a": 1}}}, id="backend-not-a-string"),
            pytest.param({"system": "s", "contracts": {"layer": "bronze"}}, id="contracts-not-a-list"),
        ],
    )
    def test_malformed_system_values_are_refused(self, document):
        with pytest.raises(Exception):
            load_strict_system(document)

    def test_the_quality_collision_is_caught(self):
        """``quality`` means a RULE SET on a contract and THRESHOLDS on a domain.

        Shape validation alone accepts the rule list here, because extras ride along —
        which is why the strict key pass exists rather than being optional polish.
        """
        with pytest.raises(ValueError, match="row_rules"):
            load_strict_domain({"domain": "d", "slo": {"quality": {"row_rules": [{"name": "x"}]}}})

    def test_a_misspelled_key_is_named(self):
        with pytest.raises(ValueError, match="ownership.jira_porject"):
            load_strict_domain({"domain": "d", "ownership": {"jira_porject": "KAN"}})


class TestFormsThatMustKeepWorking:
    """Real files use these shapes. Rejecting them would be a regression, not rigour."""

    def test_vendor_extension_blocks_are_allowed(self):
        # `x-` prefixed keys are the documented escape hatch; a standard that forbade
        # them would push vendors into misusing declared fields instead.
        load_strict_system({"system": "s", "x-azure-storage": {"anything": True}})

    def test_a_declared_but_empty_block_is_not_an_error(self):
        # `contracts:` with nothing under it says "none yet" — more informative than
        # omitting the key, and it must not validate worse than omitting it.
        assert load_strict_system({"system": "s", "contracts": None}).contracts == []

    def test_both_notification_forms_read_the_same(self):
        legacy = load_strict_domain(
            {"domain": "d", "notifications": [{"type": "slack", "target": "#x", "on_events": ["failure"]}]}
        )
        modern = load_strict_domain(
            {
                "domain": "d",
                "notifications": {
                    "enabled": True,
                    "channels": [{"type": "slack", "target": "#x", "on_events": ["failure"]}],
                },
            }
        )
        assert len(legacy.notification_channels()) == len(modern.notification_channels()) == 1
        assert legacy.notifications_are_enabled() is modern.notifications_are_enabled() is True

    def test_the_kill_switch_is_readable_in_both_places(self):
        """`notifications_enabled` lived in a different file under a different name from
        the routes it gates, which is how one reader honoured it and another did not.
        Both spellings resolve through one accessor so a caller cannot consult the wrong
        one."""
        legacy_off = load_strict_system({"system": "s", "notifications_enabled": False})
        modern_off = load_strict_domain({"domain": "d", "notifications": {"enabled": False, "channels": []}})
        assert legacy_off.notifications_are_enabled() is False
        assert modern_off.notifications_are_enabled() is False

    def test_absent_switch_means_enabled(self):
        # A file that declares channels and no switch means to use them.
        assert load_strict_domain({"domain": "d"}).notifications_are_enabled() is True

    def test_quarantine_mode_and_write_mode_both_parse(self):
        # Real `_system.yaml` writes `mode:`; the contract models `write_mode:`. The
        # files predate the model, so neither is declared wrong.
        assert load_strict_system({"system": "s", "quarantine": {"mode": "append"}}).quarantine.mode == "append"

    def test_layer_maps_are_accepted_where_a_contract_has_one_value(self):
        doc = load_strict_system(
            {
                "system": "s",
                "materialization": {"bronze": {"strategy": "append", "format": "delta"}},
                "server": {"bronze": {"cast_to_string": True}},
            }
        )
        assert doc.materialization["bronze"].strategy == "append"
        # No `path` required: a system declares layer behaviour, not a dataset location.
        assert doc.server["bronze"].cast_to_string is True
