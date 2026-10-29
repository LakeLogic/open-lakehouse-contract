"""Business map fields: ``entity`` (contract), ``identifies`` / ``role`` (column), and the
domain file's ``concepts`` / ``relationships``.

All optional. A contract or domain file without them must validate exactly as before; with
them, the values must round-trip unchanged.

unittest, not pytest: ``tests/`` runs under ``python -m unittest discover``.
"""

from __future__ import annotations

import copy
import unittest
from pathlib import Path

from olc.models import OLCContractV1, load_strict
from olc.models.registry_v1 import load_strict_domain
from olc.yaml_compat import safe_load

ROOT = Path(__file__).resolve().parents[1]

_CONTRACT = {
    "version": "1.0.0",
    "info": {"title": "Payments"},
    "model": {
        "fields": [
            {"name": "payment_id", "type": "string"},
            {"name": "trip_id", "type": "string"},
        ]
    },
    "primary_key": ["payment_id"],
}


class ContractFieldsTest(unittest.TestCase):
    def test_old_contract_unchanged(self) -> None:
        contract = load_strict(copy.deepcopy(_CONTRACT))
        self.assertIsNone(contract.entity)
        self.assertIsNone(contract.model.fields[0].identifies)
        self.assertIsNone(contract.model.fields[0].role)
        dumped = contract.model_dump(exclude_unset=True)
        self.assertNotIn("entity", dumped)
        self.assertNotIn("identifies", dumped["model"]["fields"][0])

    def test_valid_examples_still_validate(self) -> None:
        for path in sorted((ROOT / "tests" / "valid").glob("*.yaml")):
            with self.subTest(path=path.name):
                OLCContractV1.model_validate(safe_load(path.read_text("utf-8")))

    def test_round_trip(self) -> None:
        doc = copy.deepcopy(_CONTRACT)
        doc["entity"] = "Payment"
        doc["model"]["fields"][1].update(identifies="Trip", role="paid_for")
        contract = load_strict(doc)
        self.assertEqual(contract.entity, "Payment")
        dumped = contract.model_dump(exclude_unset=True)
        self.assertEqual(dumped["entity"], "Payment")
        self.assertEqual(dumped["model"]["fields"][1]["identifies"], "Trip")
        self.assertEqual(dumped["model"]["fields"][1]["role"], "paid_for")
        self.assertEqual(load_strict(dumped).model_dump(exclude_unset=True), dumped)

    def test_misspelled_key_still_refused(self) -> None:
        doc = copy.deepcopy(_CONTRACT)
        doc["entitty"] = "Payment"
        with self.assertRaises(Exception):
            load_strict(doc)


class DomainFileTest(unittest.TestCase):
    def test_old_domain_unchanged(self) -> None:
        domain = load_strict_domain({"domain": "marketplace"})
        self.assertEqual(domain.concepts, {})
        self.assertEqual(domain.relationships, [])

    def test_declared_but_empty(self) -> None:
        domain = load_strict_domain(
            {"domain": "marketplace", "concepts": None, "relationships": None}
        )
        self.assertEqual(domain.concepts, {})
        self.assertEqual(domain.relationships, [])

    def test_round_trip(self) -> None:
        doc = {
            "domain": "marketplace",
            "concepts": {
                "Customer": {
                    "definition": "A person who requests trips.",
                    "also_called": ["Rider", "Passenger"],
                    "not_to_be_confused_with": "Driver",
                    "identifier": "customer_id",
                    "example": "C-1001",
                },
                "Trip": {"definition": "A journey from pickup to drop-off."},
            },
            "relationships": [
                {"from": "Customer", "verb": "books", "to": "Trip", "cardinality": "one_to_many"},
                {"from": "Trip", "verb": "has", "to": "Payment"},
            ],
        }
        domain = load_strict_domain(doc)
        self.assertEqual(domain.concepts["Customer"].also_called, ["Rider", "Passenger"])
        self.assertEqual(domain.relationships[0].from_, "Customer")
        self.assertEqual(domain.relationships[1].cardinality, "unknown")
        dumped = domain.model_dump(by_alias=True, exclude_unset=True)
        self.assertEqual(dumped["relationships"][0]["from"], "Customer")
        self.assertEqual(dumped["concepts"], doc["concepts"])
        self.assertEqual(
            load_strict_domain(dumped).model_dump(by_alias=True, exclude_unset=True),
            dumped,
        )

    def test_bad_cardinality_refused(self) -> None:
        with self.assertRaises(Exception):
            load_strict_domain(
                {
                    "relationships": [
                        {"from": "A", "verb": "has", "to": "B", "cardinality": "lots"}
                    ]
                }
            )

    def test_misspelled_concept_key_refused(self) -> None:
        with self.assertRaises(Exception):
            load_strict_domain({"concepts": {"Customer": {"defintion": "x"}}})


_STORY = {
    "actors": ["Customer", "Warehouse"],
    "steps": [
        {"id": "order", "actor": "Customer", "text": "Customer places an order", "concepts": ["Order"]},
        {"id": "ship", "actor": "Warehouse", "text": "Warehouse ships the order",
         "concepts": ["Shipment", "Order"], "after": ["order"]},
        {"id": "cancel", "actor": "Customer", "text": "Customer cancels the order",
         "after": ["order"], "kind": "branch"},
        {"id": "pack", "actor": "Warehouse", "text": "Warehouse packs the parcel",
         "after": ["order"], "kind": "gap", "note": "No data contract records packing."},
    ],
}


class DomainStoryTest(unittest.TestCase):
    def test_old_domain_has_no_story(self) -> None:
        self.assertIsNone(load_strict_domain({"domain": "shop"}).story)

    def test_round_trip(self) -> None:
        domain = load_strict_domain({"domain": "shop", "story": copy.deepcopy(_STORY)})
        story = domain.story
        assert story is not None
        self.assertEqual([s.id for s in story.steps], ["order", "ship", "cancel", "pack"])
        self.assertEqual(story.steps[0].kind, "step")
        self.assertEqual(story.steps[0].after, [])
        self.assertEqual(story.steps[3].kind, "gap")
        dumped = domain.model_dump(by_alias=True, exclude_unset=True)
        self.assertEqual(dumped["story"], _STORY)
        self.assertEqual(
            load_strict_domain(dumped).model_dump(by_alias=True, exclude_unset=True), dumped
        )

    def test_declared_but_empty(self) -> None:
        story = load_strict_domain({"story": {"actors": None, "steps": None}}).story
        assert story is not None
        self.assertEqual((story.actors, story.steps), ([], []))

    def _refused(self, mutate) -> None:
        doc = copy.deepcopy(_STORY)
        mutate(doc)
        with self.assertRaises(Exception):
            load_strict_domain({"story": doc})

    def test_unknown_predecessor_refused(self) -> None:
        self._refused(lambda d: d["steps"][1].update(after=["nope"]))

    def test_duplicate_id_refused(self) -> None:
        self._refused(lambda d: d["steps"][1].update(id="order"))

    def test_actor_not_in_actors_refused(self) -> None:
        self._refused(lambda d: d["steps"][1].update(actor="Courier"))

    def test_bad_kind_refused(self) -> None:
        self._refused(lambda d: d["steps"][1].update(kind="maybe"))

    def test_misspelled_step_key_refused(self) -> None:
        self._refused(lambda d: d["steps"][1].update(aftr=["order"]))


if __name__ == "__main__":
    unittest.main()
