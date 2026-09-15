"""Data products: the contract reference and the domain's product definitions.

A product is defined ONCE, in its domain's ``_domain.yaml`` ``products:`` list, with a stable
``id``. A contract names the product that publishes it with ``info.data_product`` (and,
optionally, which expected output it implements with ``info.data_product_output``).

Before this, ``info.data_product`` was silently dropped by the model and rejected by the strict
contract, and ``products:`` was rejected by the strict domain loader — so products lived in
``metadata`` as free-text names that broke on rename.

unittest, not pytest: ``tests/`` runs under ``python -m unittest discover``.
"""

from __future__ import annotations

import copy
import unittest

from olc.models import OLCContractV1
from olc.models._nested import Info
from olc.models.registry_v1 import load_strict_domain

_CONTRACT = {
    "version": "1.0.0",
    "info": {
        "title": "Monthly Property Income",
        "table_name": "gold_property_monthly_income",
    },
    "model": {"fields": [{"name": "property_id", "type": "string"}]},
}

_DOMAIN = {
    "domain": "real_estate",
    "products": [
        {
            "id": "property_performance",
            "name": "Property Performance",
            "description": "Monthly property income, expenses and operating performance.",
            "owner": "property_data_team",
            "lifecycle": "active",
            "expected_outputs": [
                {
                    "id": "monthly_property_income",
                    "name": "Monthly Property Income",
                    "kind": "table",
                },
                {"id": "operating_expenses", "name": "Operating Expenses"},
                {"id": "property_dimension", "name": "Property Dimension"},
                {
                    "id": "occupancy_model",
                    "name": "Occupancy model",
                    "kind": "semantic_model",
                    "required": False,
                },
            ],
        }
    ],
}


def _contract(**info: object) -> dict:
    doc = copy.deepcopy(_CONTRACT)
    doc["info"].update(info)
    return doc


def _domain(mutate=None) -> dict:
    doc = copy.deepcopy(_DOMAIN)
    if mutate:
        mutate(doc)
    return doc


class ContractReferenceTests(unittest.TestCase):
    def test_the_reference_is_kept_not_dropped(self) -> None:
        info = Info.model_validate(
            {
                "title": "t",
                "data_product": "property_performance",
                "data_product_output": "operating_expenses",
            }
        )
        self.assertEqual(info.data_product, "property_performance")
        self.assertEqual(info.data_product_output, "operating_expenses")

    def test_strict_contract_accepts_a_product_and_output(self) -> None:
        model = OLCContractV1.model_validate(
            _contract(
                data_product="property_performance",
                data_product_output="monthly_property_income",
            )
        )
        self.assertEqual(model.info.data_product, "property_performance")

    def test_a_product_without_an_output_is_valid(self) -> None:
        OLCContractV1.model_validate(_contract(data_product="property_performance"))

    def test_a_contract_with_no_product_is_valid(self) -> None:
        # Unassigned and supporting assets are legitimate; membership is a policy, not a schema rule.
        OLCContractV1.model_validate(_contract())

    def test_other_unknown_info_keys_are_still_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "info.data_products"):
            OLCContractV1.model_validate(
                _contract(data_products="property_performance")
            )

    def test_a_display_name_is_not_an_id(self) -> None:
        # A name breaks on rename; the reference must be the stable id.
        for bad in ("Property Performance", "property-performance", "1property", "p"):
            with (
                self.subTest(value=bad),
                self.assertRaisesRegex(ValueError, "info.data_product must be"),
            ):
                OLCContractV1.model_validate(_contract(data_product=bad))

    def test_an_output_needs_a_product(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires info.data_product"):
            OLCContractV1.model_validate(
                _contract(data_product_output="operating_expenses")
            )

    def test_the_runtime_path_does_not_enforce_the_format(self) -> None:
        # The lenient runtime re-uses Info: a malformed value must not fail its parse.
        self.assertEqual(
            Info.model_validate(
                {"title": "t", "data_product": "Legacy Name"}
            ).data_product,
            "Legacy Name",
        )


class DomainProductTests(unittest.TestCase):
    def test_a_domain_with_products_validates_strictly(self) -> None:
        domain = load_strict_domain(_domain())
        product = domain.products[0]
        self.assertEqual(product.id, "property_performance")
        self.assertEqual(
            [o.id for o in product.expected_outputs][:1], ["monthly_property_income"]
        )
        self.assertTrue(product.expected_outputs[0].required)
        self.assertFalse(product.expected_outputs[3].required)

    def test_a_domain_without_products_still_validates(self) -> None:
        self.assertEqual(load_strict_domain({"domain": "real_estate"}).products, [])

    def test_declared_but_empty_products_means_none(self) -> None:
        self.assertEqual(
            load_strict_domain({"domain": "real_estate", "products": None}).products, []
        )

    def test_lifecycle_defaults_to_proposed(self) -> None:
        domain = load_strict_domain(
            {"domain": "d", "products": [{"id": "p_one", "name": "P"}]}
        )
        self.assertEqual(domain.products[0].lifecycle, "proposed")

    def test_wrong_product_definitions_are_refused(self) -> None:
        def drop_id(doc):
            del doc["products"][0]["id"]

        def bad_slug(doc):
            doc["products"][0]["id"] = "Property Performance"

        def bad_lifecycle(doc):
            doc["products"][0]["lifecycle"] = "live"

        def bad_kind(doc):
            doc["products"][0]["expected_outputs"][0]["kind"] = "spreadsheet"

        def duplicate_product(doc):
            doc["products"].append({"id": "property_performance", "name": "Again"})

        def duplicate_output(doc):
            doc["products"][0]["expected_outputs"].append(
                {"id": "operating_expenses", "name": "Again"}
            )

        def typo_key(doc):
            doc["products"][0]["expected_ouputs"] = []

        cases = {
            "missing id": drop_id,
            "name used as id": bad_slug,
            "unknown lifecycle": bad_lifecycle,
            "unknown output kind": bad_kind,
            "duplicate product id": duplicate_product,
            "duplicate output id": duplicate_output,
            "misspelled key": typo_key,
        }
        for label, mutate in cases.items():
            with self.subTest(case=label), self.assertRaises(ValueError):
                load_strict_domain(_domain(mutate))

    def test_vendor_extension_keys_on_a_product_are_allowed(self) -> None:
        def add_vendor(doc):
            doc["products"][0]["x-catalog-id"] = "abc"

        load_strict_domain(_domain(add_vendor))


if __name__ == "__main__":
    unittest.main()
