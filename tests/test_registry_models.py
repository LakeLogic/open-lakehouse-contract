"""``_domain.yaml`` and ``_system.yaml`` validate against the standard.

Before these models the only check either file received was ``yaml.safe_load`` — and the
config editor reported that to the user as "valid". A misspelled ``on_events`` token, a
channel routing nowhere, a ``run_log_backend`` typo: all passed, and the failure surfaced
later as an alert that never arrived.

Two things have to hold together, and one without the other is worthless:

* every real file in the estate still validates — a model that rejects working
  configuration is not stricter, it is broken; and
* configuration that is genuinely wrong is rejected — a model that accepts everything
  reproduces the ``safe_load`` situation with more ceremony.

unittest, not pytest: ``tests/`` runs under ``python -m unittest discover`` with only
``pip install -e .[models]``; pytest is installed for ``conformance/`` alone.
"""

from __future__ import annotations

import glob
import unittest
from pathlib import Path

from olc.models.registry_v1 import (
    NOTIFICATION_EVENT_TOKENS,
    canonical_event,
    load_strict_domain,
    load_strict_system,
)
from olc.yaml_compat import safe_load

# The estate this standard has to keep working. Absolute paths because the corpus lives in
# sibling working copies; in CI they are absent and the corpus tests SKIP rather than fail,
# so the suite stays portable. A skip is honest here — it says the estate was not checked,
# where a silent pass would claim it was.
_CORPORA = [
    Path("C:/_Personal/_SaaS/LakeLogic_SaaS/src/api/demo_assets"),
    Path("C:/_Personal/_SaaS/lakelogic/examples"),
    Path("C:/_Personal/_SaaS/lakelogic-databricks-data-mesh-lakehouse"),
    Path("C:/_Personal/_SaaS/lakelogic-microsoft-fabric-data-mesh-lakehouse"),
    Path("C:/_Personal/_SaaS/lakelogic-snowflake-data-mesh-lakehouse"),
]


def _files(kind: str) -> list:
    found: list = []
    for root in _CORPORA:
        if root.exists():
            found += sorted(
                glob.glob(str(root / "**" / f"_{kind}.yaml"), recursive=True)
            )
    return found


def _load(path: str) -> dict:
    # `safe_load` from olc.yaml_compat, not PyYAML's: the standard has to read a document
    # the way the runtime does, or it validates a file nobody actually runs.
    with open(path, encoding="utf-8") as handle:
        return safe_load(handle) or {}


class RealEstateTests(unittest.TestCase):
    """Every file that exists today must keep validating."""

    def _check_all(self, kind: str, loader) -> None:
        paths = _files(kind)
        if not paths:
            self.skipTest(f"no _{kind}.yaml corpus on this machine")
        for path in paths:
            with self.subTest(path=path):
                loader(_load(path))

    def test_every_real_domain_file_validates_strictly(self) -> None:
        self._check_all("domain", load_strict_domain)

    def test_every_real_system_file_validates_strictly(self) -> None:
        self._check_all("system", load_strict_system)


class RejectsWhatIsActuallyWrongTests(unittest.TestCase):
    """The half that makes the models worth having."""

    def test_malformed_domain_values_are_refused(self) -> None:
        cases = {
            "retention-not-a-duration": {"domain": "d", "retention": {"bronze": 7}},
            "contacts-not-a-list": {
                "domain": "d",
                "ownership": {"contacts": "me@x.com"},
            },
            "budget-not-a-number": {
                "domain": "d",
                "cost": {"budget": {"daily_limit": "forty"}},
            },
            "enabled-not-a-bool": {
                "domain": "d",
                "observatory": {"enabled": "yes-please"},
            },
        }
        for label, document in cases.items():
            with self.subTest(case=label), self.assertRaises(Exception):
                load_strict_domain(document)

    def test_malformed_system_values_are_refused(self) -> None:
        cases = {
            "backend-not-a-string": {
                "system": "s",
                "metadata": {"run_log_backend": {"a": 1}},
            },
            "contracts-not-a-list": {"system": "s", "contracts": {"layer": "bronze"}},
        }
        for label, document in cases.items():
            with self.subTest(case=label), self.assertRaises(Exception):
                load_strict_system(document)

    def test_the_quality_collision_is_caught(self) -> None:
        """``quality`` means a RULE SET on a contract and THRESHOLDS on a domain.

        Shape validation alone accepts the rule list here, because extras ride along —
        which is why the strict key pass exists rather than being optional polish.
        """
        with self.assertRaisesRegex(ValueError, "row_rules"):
            load_strict_domain(
                {"domain": "d", "slo": {"quality": {"row_rules": [{"name": "x"}]}}}
            )

    def test_a_misspelled_key_is_named(self) -> None:
        with self.assertRaisesRegex(ValueError, "ownership.jira_porject"):
            load_strict_domain({"domain": "d", "ownership": {"jira_porject": "KAN"}})


class FormsThatMustKeepWorkingTests(unittest.TestCase):
    """Real files use these shapes. Rejecting them would be a regression, not rigour."""

    def test_vendor_extension_blocks_are_allowed(self) -> None:
        # `x-` prefixed keys are the documented escape hatch; forbidding them would push
        # vendors into misusing declared fields instead.
        load_strict_system({"system": "s", "x-azure-storage": {"anything": True}})

    def test_a_declared_but_empty_block_is_not_an_error(self) -> None:
        # `contracts:` with nothing under it says "none yet" — more informative than
        # omitting the key, and it must not validate worse than omitting it.
        self.assertEqual(
            load_strict_system({"system": "s", "contracts": None}).contracts, []
        )

    def test_both_notification_forms_read_the_same(self) -> None:
        channel = {"type": "slack", "target": "#x", "on_events": ["failure"]}
        legacy = load_strict_domain({"domain": "d", "notifications": [channel]})
        modern = load_strict_domain(
            {"domain": "d", "notifications": {"enabled": True, "channels": [channel]}}
        )
        self.assertEqual(len(legacy.notification_channels()), 1)
        self.assertEqual(len(modern.notification_channels()), 1)
        self.assertTrue(legacy.notifications_are_enabled())
        self.assertTrue(modern.notifications_are_enabled())

    def test_the_kill_switch_is_readable_in_both_places(self) -> None:
        """`notifications_enabled` lived in a different file under a different name from
        the routes it gates, which is how one reader honoured it and another did not.
        Both spellings resolve through one accessor so a caller cannot consult the wrong
        one."""
        legacy_off = load_strict_system({"system": "s", "notifications_enabled": False})
        modern_off = load_strict_domain(
            {"domain": "d", "notifications": {"enabled": False, "channels": []}}
        )
        self.assertFalse(legacy_off.notifications_are_enabled())
        self.assertFalse(modern_off.notifications_are_enabled())

    def test_absent_switch_means_enabled(self) -> None:
        # A file that declares channels and no switch means to use them.
        self.assertTrue(load_strict_domain({"domain": "d"}).notifications_are_enabled())

    def test_quarantine_mode_and_write_mode_both_parse(self) -> None:
        # Real `_system.yaml` writes `mode:`; the contract models `write_mode:`. The files
        # predate the model, so neither is declared wrong.
        doc = load_strict_system({"system": "s", "quarantine": {"mode": "append"}})
        self.assertEqual(doc.quarantine.mode, "append")

    def test_layer_maps_are_accepted_where_a_contract_has_one_value(self) -> None:
        doc = load_strict_system(
            {
                "system": "s",
                "materialization": {
                    "bronze": {"strategy": "append", "format": "delta"}
                },
                "server": {"bronze": {"cast_to_string": True}},
            }
        )
        self.assertEqual(doc.materialization["bronze"].strategy, "append")
        # No `path` required: a system declares layer behaviour, not a dataset location.
        self.assertTrue(doc.server["bronze"].cast_to_string)


class EventVocabularyTests(unittest.TestCase):
    """One list of event names, readable by the router, the editor and the file.

    It was written down three times and agreed nowhere: the routing service kept an alias
    table, the config editor offered a chip list, and the files used a third set. `failed`
    fires but was missing from the chips (so it rendered unselected and was dropped on
    save); `slo_recovery`, `dataset_rule_failed` and `partial` are offered by the chips and
    matched by nothing (so choosing one produces a channel that never fires).
    """

    def _doc(self, token: str) -> dict:
        return {
            "domain": "d",
            "notifications": [
                {"type": "email", "targets": ["a@b.c"], "on_events": [token]}
            ],
        }

    def test_spellings_the_router_honours_are_accepted(self) -> None:
        # 24 real files said `failed`. A standard that invalidates a working estate to
        # tidy its own spelling is not stricter, it is wrong.
        for token in ("failed", "failure", "slo_breach", "quarantine", "all", "*"):
            with self.subTest(token=token):
                load_strict_domain(self._doc(token))

    def test_tokens_nothing_matches_are_refused(self) -> None:
        # Including the three the editor used to offer: a chip that cannot fire is a label
        # promising a capability the surface does not have.
        for token in (
            "faled",
            "slo_recovery",
            "dataset_rule_failed",
            "partial",
            "nonsense",
        ):
            with self.subTest(token=token), self.assertRaises(Exception):
                load_strict_domain(self._doc(token))

    def test_canonical_event_maps_every_accepted_spelling(self) -> None:
        for token in NOTIFICATION_EVENT_TOKENS - {"all", "*"}:
            with self.subTest(token=token):
                self.assertIsNotNone(canonical_event(token))


class QualityCoverageTests(unittest.TestCase):
    """``quality_coverage``: per-layer expectations a platform scores contracts against."""

    FULL = {
        "silver": {"field_check_target": 0.7},
        "gold": {"require": ["grain_unique", "referential_integrity"]},
    }

    def test_full_block_validates_on_domain_and_system(self) -> None:
        domain = load_strict_domain({"domain": "d", "quality_coverage": self.FULL})
        self.assertEqual(domain.quality_coverage.silver.field_check_target, 0.7)
        self.assertEqual(
            domain.quality_coverage.gold.require,
            ["grain_unique", "referential_integrity"],
        )
        system = load_strict_system({"system": "s", "quality_coverage": self.FULL})
        self.assertEqual(system.quality_coverage.silver.field_check_target, 0.7)

    def test_every_part_is_optional(self) -> None:
        for block in ({}, {"silver": {}}, {"gold": {}}, {"gold": {"require": []}}):
            with self.subTest(block=block):
                load_strict_domain({"domain": "d", "quality_coverage": block})

    def test_bad_values_are_refused(self) -> None:
        cases = {
            "target-above-one": {"silver": {"field_check_target": 1.5}},
            "target-negative": {"silver": {"field_check_target": -0.1}},
            "target-a-percent-string": {"silver": {"field_check_target": "70%"}},
            "unknown-gold-check": {"gold": {"require": ["three_rules"]}},
            "require-not-a-list": {"gold": {"require": "grain_unique"}},
            "typo-key": {"silver": {"field_target": 0.7}},
        }
        for label, block in cases.items():
            with self.subTest(case=label), self.assertRaises(Exception):
                load_strict_domain({"domain": "d", "quality_coverage": block})


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


class QuarantineTableNameTests(unittest.TestCase):
    """`storage.quarantine_table_name` is standard: the runtime honoured it and Build Centre
    emits it, but strict validation rejected every system file carrying it (2026-10-01)."""

    def test_a_system_may_name_its_quarantine_tables(self):
        doc = load_strict_system(
            {
                "domain": "marketing",
                "system": "google_ads",
                "storage": {
                    "quarantine_root": "`{catalog}`.{domain}",
                    "quarantine_table_name": "quarantine_{table}",
                },
            }
        )
        self.assertEqual(doc.storage.quarantine_table_name, "quarantine_{table}")


class StudioRegistryKeys(unittest.TestCase):
    """Studio writes, and the runtime reads, `storage_mode`, `metadata.platform` and the
    environment's project, log and landing locations. Strict validation rejected every system
    file carrying them, so editing any RideFlow `_system.yaml` failed review (2026-11-01)."""

    def test_a_system_may_declare_its_layout_keys(self):
        doc = load_strict_system(
            {
                "system": "rideflow",
                "storage_mode": "catalog",
                "metadata": {"run_log_backend": "spark", "platform": "fabric"},
                "environments": {
                    "dev": {
                        "project_root": "rideflow_dev",
                        "log_path": "/Volumes/rideflow_dev_{domain}/files/lakelogic_logs",
                        "landing_path": "@RIDEFLOW_DEV_{domain}.FILES.LANDING/{system}",
                        "ls_catalog": "rideflow_dev",
                        "ls_schema": "files",
                        "ls_volume": "landing",
                        "ls_folder": "",
                    }
                },
            }
        )
        self.assertEqual(doc.storage_mode, "catalog")
        self.assertEqual(doc.metadata.platform, "fabric")
        self.assertEqual(doc.environments["dev"].ls_volume, "landing")


class SourceSystemBlockTests(unittest.TestCase):
    """``source_system`` says what a system IS (2026-11-26): name, kind, vendor, formats."""

    def test_a_declared_source_system_validates(self) -> None:
        model = load_strict_system(
            {
                "system": "google_analytics",
                "source_system": {
                    "name": "Google Analytics 4",
                    "kind": "saas_api",
                    "vendor": "Google",
                    "formats": ["json"],
                    "connection": "ga4-prod",
                    "owner": "Growth Analytics",
                    "description": "Web and app events",
                },
            }
        )
        self.assertEqual(model.source_system.name, "Google Analytics 4")
        self.assertEqual(model.source_system.kind, "saas_api")
        self.assertEqual(model.source_system.formats, ["json"])

    def test_a_system_without_the_block_still_validates(self) -> None:
        self.assertIsNone(load_strict_system({"system": "s"}).source_system)

    def test_an_unknown_kind_is_refused_naming_the_allowed_values(self) -> None:
        with self.assertRaisesRegex(Exception, "saas_api"):
            load_strict_system({"system": "s", "source_system": {"kind": "crm"}})

    def test_an_unknown_format_is_refused(self) -> None:
        with self.assertRaisesRegex(Exception, "parquet"):
            load_strict_system({"system": "s", "source_system": {"formats": ["mp3"]}})

    def test_document_formats_are_accepted(self) -> None:
        model = load_strict_system(
            {
                "system": "checkr",
                "source_system": {"formats": ["csv", "pdf", "docx", "image"]},
            }
        )
        self.assertEqual(model.source_system.formats, ["csv", "pdf", "docx", "image"])

    def test_a_misspelled_key_inside_the_block_is_named(self) -> None:
        with self.assertRaisesRegex(ValueError, "source_system.vendr"):
            load_strict_system({"system": "s", "source_system": {"vendr": "Sage"}})
