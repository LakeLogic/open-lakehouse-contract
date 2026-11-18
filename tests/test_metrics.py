"""Declared metrics (ontology-metrics-v1): the one definition of a valid `metrics:` block."""

import pytest

from olc.models import OLCContractV1
from olc.models.metrics import expression_names, metric_problems

FIELDS = ["trip_id", "gross_revenue_amount", "trip_count", "dropoff_date", "trip_type"]


def _contract(metrics):
    return {"version": "1.0.0", "info": {"title": "Gold Fact Revenue Daily"},
            "model": {"fields": [{"name": f, "type": "string"} for f in FIELDS]}, "metrics": metrics}


def test_a_valid_block_is_accepted_with_base_and_derived_metrics():
    c = OLCContractV1.model_validate(_contract([
        {"name": "Revenue", "of": "Trip", "expression": "SUM(gross_revenue_amount)", "unit": "GBP"},
        {"name": "Trips", "expression": "SUM(trip_count)"},
        {"name": "Revenue per trip", "expression": "Revenue / Trips", "additivity": "non_additive",
         "dimensions": ["trip_type"], "date_column": "dropoff_date"},
    ]))
    assert [m.name for m in c.metrics] == ["Revenue", "Trips", "Revenue per trip"]


def test_a_missing_column_names_the_metric_and_the_column():
    with pytest.raises(ValueError, match="metric 'Revenue' names column 'net_amount'"):
        OLCContractV1.model_validate(_contract([{"name": "Revenue", "expression": "SUM(net_amount)"}]))


def test_a_metric_referring_to_itself_directly_or_through_another_is_refused():
    assert metric_problems([{"name": "Loop", "expression": "Loop / 2"}], FIELDS) == ["metric 'Loop' refers to itself"]
    problems = metric_problems([{"name": "A", "expression": "B + 1"}, {"name": "B", "expression": "A * 2"}], FIELDS)
    assert any("refers to itself through" in p for p in problems)


def test_unknown_keys_dimensions_and_duplicates_are_refused():
    with pytest.raises(ValueError):
        OLCContractV1.model_validate(_contract([{"name": "X", "expression": "COUNT(*)", "colour": "red"}]))
    assert "metric 'X' lists dimension 'city'" in metric_problems(
        [{"name": "X", "expression": "COUNT(*)", "dimensions": ["city"]}], FIELDS)[0]
    assert "declared more than once" in metric_problems(
        [{"name": "X", "expression": "COUNT(*)"}, {"name": "x", "expression": "COUNT(*)"}], FIELDS)[0]


def test_expressions_read_functions_words_strings_and_spaced_metric_names():
    used, cols = expression_names(
        "SUM(CASE WHEN trip_type = 'eats delivery' THEN gross_revenue_amount ELSE 0 END) / NULLIF(Fare total, 0)",
        ["Fare total"])
    assert used == {"Fare total"} and cols == {"trip_type", "gross_revenue_amount"}


def test_a_contract_without_metrics_is_unchanged():
    assert OLCContractV1.model_validate(_contract([])).metrics == []


def test_a_metric_named_like_its_column_aggregates_the_column_not_itself():
    assert metric_problems([{"name": "Fare", "expression": "SUM(fare)"}], ["fare"]) == []
