"""Declared metrics (ontology-metrics-v1): the one definition of a valid `metrics:` block."""

import pytest

from olc.models import OLCContractV1
from olc.models.metrics import Metric, expression_names, metric_problems

FIELDS = ["trip_id", "gross_revenue_amount", "trip_count", "dropoff_date", "trip_type"]


def _contract(metrics):
    return {
        "version": "1.0.0",
        "info": {"title": "Gold Fact Revenue Daily"},
        "model": {"fields": [{"name": f, "type": "string"} for f in FIELDS]},
        "metrics": metrics,
    }


def test_a_valid_block_is_accepted_with_base_and_derived_metrics():
    c = OLCContractV1.model_validate(
        _contract(
            [
                {
                    "name": "Revenue",
                    "of": "Trip",
                    "expression": "SUM(gross_revenue_amount)",
                    "unit": "GBP",
                },
                {"name": "Trips", "expression": "SUM(trip_count)"},
                {
                    "name": "Revenue per trip",
                    "expression": "Revenue / Trips",
                    "additivity": "non_additive",
                    "dimensions": ["trip_type"],
                    "date_column": "dropoff_date",
                },
            ]
        )
    )
    assert [m.name for m in c.metrics] == ["Revenue", "Trips", "Revenue per trip"]


def test_a_missing_column_names_the_metric_and_the_column():
    with pytest.raises(ValueError, match="metric 'Revenue' names column 'net_amount'"):
        OLCContractV1.model_validate(
            _contract([{"name": "Revenue", "expression": "SUM(net_amount)"}])
        )


def test_a_metric_referring_to_itself_directly_or_through_another_is_refused():
    assert metric_problems([{"name": "Loop", "expression": "Loop / 2"}], FIELDS) == [
        "metric 'Loop' refers to itself"
    ]
    problems = metric_problems(
        [{"name": "A", "expression": "B + 1"}, {"name": "B", "expression": "A * 2"}],
        FIELDS,
    )
    assert any("refers to itself through" in p for p in problems)


def test_unknown_keys_dimensions_and_duplicates_are_refused():
    with pytest.raises(ValueError):
        OLCContractV1.model_validate(
            _contract([{"name": "X", "expression": "COUNT(*)", "colour": "red"}])
        )
    assert (
        "metric 'X' lists dimension 'city'"
        in metric_problems(
            [{"name": "X", "expression": "COUNT(*)", "dimensions": ["city"]}], FIELDS
        )[0]
    )
    assert (
        "declared more than once"
        in metric_problems(
            [
                {"name": "X", "expression": "COUNT(*)"},
                {"name": "x", "expression": "COUNT(*)"},
            ],
            FIELDS,
        )[0]
    )


def test_expressions_read_functions_words_strings_and_spaced_metric_names():
    used, cols = expression_names(
        "SUM(CASE WHEN trip_type = 'eats delivery' THEN gross_revenue_amount ELSE 0 END) / NULLIF(Fare total, 0)",
        ["Fare total"],
    )
    assert used == {"Fare total"} and cols == {"trip_type", "gross_revenue_amount"}


def test_a_contract_without_metrics_is_unchanged():
    assert OLCContractV1.model_validate(_contract([])).metrics == []


def test_a_metric_named_like_its_column_aggregates_the_column_not_itself():
    assert (
        metric_problems([{"name": "Fare", "expression": "SUM(fare)"}], ["fare"]) == []
    )


# ── structured metrics (2026-11-27, docs/specs/structured-metrics.md) ────────

from olc.models.metrics import derived_additivity, metric_expression, metric_sql  # noqa: E402

CASES = [
    "Id",
    "CreatedDate",
    "ClosedDate",
    "Status_sk",
    "fare_amount",
    "currency",
    "surge_rate",
    "trip_type",
]
TYPES = {
    "Id": "string",
    "CreatedDate": "timestamp",
    "ClosedDate": "date",
    "Status_sk": "string",
    "fare_amount": "decimal(10,2)",
    "currency": "string",
    "surge_rate": "double",
    "trip_type": "string",
}
CLOSED = {
    "name": "Closed cases",
    "aggregation": "count_distinct",
    "expr": "Id",
    "filter": "ClosedDate IS NOT NULL",
    "date_column": "ClosedDate",
}
TOTAL = {
    "name": "Total cases",
    "aggregation": "count_distinct",
    "expr": "Id",
    "date_column": "CreatedDate",
}
RATE = {
    "name": "Case closure rate",
    "type": "ratio",
    "numerator": "Closed cases",
    "denominator": "Total cases",
    "format": "0.0%",
}


def _problems(ms, **kw):
    return metric_problems(
        ms,
        CASES,
        field_types=TYPES,
        keys=kw.get("keys", ["Id"]),
        references=kw.get("refs", ["Status_sk"]),
    )


def test_parts_and_ratio_are_accepted_and_expression_is_generated():
    assert _problems([CLOSED, TOTAL, RATE]) == []
    assert (
        metric_expression(CLOSED)
        == "COUNT(DISTINCT CASE WHEN ClosedDate IS NOT NULL THEN Id END)"
    )
    rate = metric_expression(RATE, [CLOSED, TOTAL, RATE])
    assert rate == (
        "(COUNT(DISTINCT CASE WHEN ClosedDate IS NOT NULL THEN Id END)) / "
        "NULLIF((COUNT(DISTINCT Id)), 0)"
    )  # zero denominator: no data, never 0


def test_parts_and_expression_together_or_neither_are_refused():
    with pytest.raises(ValueError, match="both parts and an expression"):
        Metric.model_validate({**CLOSED, "expression": "COUNT(*)"})
    with pytest.raises(ValueError, match="needs parts"):
        Metric.model_validate({"name": "Empty"})
    with pytest.raises(ValueError, match="needs a numerator and a denominator"):
        Metric.model_validate({"name": "R", "type": "ratio", "numerator": "A"})


def test_ratio_pointing_at_a_missing_or_renamed_metric_is_refused():
    renamed = {**CLOSED, "name": "Cases closed"}
    assert any(
        "numerator 'Closed cases', which is not a metric" in p
        for p in _problems([renamed, TOTAL, RATE])
    )


def test_aggregation_must_fit_the_column():
    assert any(
        "a key" in p
        for p in _problems([{"name": "X", "aggregation": "sum", "expr": "Id"}])
    )
    assert any(
        "a key" in p
        for p in _problems([{"name": "X", "aggregation": "avg", "expr": "Status_sk"}])
    )
    assert any(
        "not a number" in p
        for p in _problems([{"name": "X", "aggregation": "sum", "expr": "trip_type"}])
    )
    assert any(
        "rate or price" in p
        for p in _problems([{"name": "X", "aggregation": "sum", "expr": "surge_rate"}])
    )
    assert any(
        "aggregate in expr" in p
        for p in _problems(
            [{"name": "X", "aggregation": "sum", "expr": "SUM(fare_amount)"}]
        )
    )


def test_sum_across_currencies_is_refused_unless_broken_down_by_currency():
    plain = {"name": "Fare", "aggregation": "sum", "expr": "fare_amount"}
    assert any("across currencies" in p for p in _problems([plain]))
    assert _problems([{**plain, "dimensions": ["currency"]}]) == []


def test_additivity_is_derived_and_a_wrong_declaration_refused():
    assert (
        derived_additivity(TOTAL, ["Id"]) == "additive"
    )  # distinct count of the own key
    assert derived_additivity(RATE) == "non_additive"
    assert (
        derived_additivity({"name": "A", "aggregation": "avg", "expr": "fare_amount"})
        == "non_additive"
    )
    assert any(
        "does not add up" in p
        for p in _problems([CLOSED, TOTAL, {**RATE, "additivity": "additive"}])
    )


def test_unknown_columns_in_expr_and_filter_are_named():
    bad = {"name": "X", "aggregation": "count", "filter": "is_refund = true"}
    assert any("column 'is_refund'" in p for p in _problems([bad]))


def test_the_same_metric_gives_sql_for_every_platform():
    pytest.importorskip("sqlglot")
    for dialect in ("databricks", "tsql", "snowflake", "duckdb"):
        sql = metric_sql(CLOSED, dialect)
        # T-SQL writes COUNT_BIG(DISTINCT ...): same meaning, the platform's own word.
        assert "(DISTINCT CASE WHEN" in sql.upper() and "CLOSEDDATE" in sql.upper()


def test_untranslatable_filter_is_refused():
    pytest.importorskip("sqlglot")
    assert any(
        "filter does not parse" in p
        for p in _problems([{**CLOSED, "filter": "ClosedDate IS NOT NULL AND ("}])
    )


def test_existing_expression_metrics_keep_working():
    assert _problems([{"name": "Cases", "expression": "COUNT(*)"}]) == []
    assert metric_expression({"name": "Cases", "expression": "COUNT(*)"}) == "COUNT(*)"


def test_common_expressions_convert_to_parts_and_back():
    pytest.importorskip("sqlglot")
    from olc.models.metrics import parts_from_expression as pfe

    assert pfe("SUM(fare_amount)") == {"aggregation": "sum", "expr": "fare_amount"}
    assert pfe("COUNT(*)") == {"aggregation": "count"}
    assert pfe("COUNT(DISTINCT Id)") == {"aggregation": "count_distinct", "expr": "Id"}
    closed = pfe("COUNT(DISTINCT CASE WHEN ClosedDate IS NOT NULL THEN Id END)")
    assert closed == {
        "aggregation": "count_distinct",
        "expr": "Id",
        "filter": "NOT ClosedDate IS NULL",
    }
    assert pfe("SUM(CASE WHEN trip_type = 'ride' THEN fare ELSE 0 END)") == {
        "aggregation": "sum",
        "expr": "fare",
        "filter": "trip_type = 'ride'",
    }
    assert pfe(
        "Closed cases / NULLIF(Total cases, 0)", ["Closed cases", "Total cases"]
    ) == {"type": "ratio", "numerator": "Closed cases", "denominator": "Total cases"}
    assert pfe("Revenue / Trips", ["Revenue", "Trips"])["type"] == "ratio"
    # Not a common shape: stays an expression.
    assert (
        pfe("SUM(a) - SUM(b)") is None
        and pfe("AVG(DATEDIFF(day, a, b))")["aggregation"] == "avg"
    )
    # Round trip: the parts give back an equivalent aggregate.
    assert "COUNT(DISTINCT CASE WHEN" in metric_expression({"name": "C", **closed})


def test_value_names_carry_meaning_and_must_name_allowed_values():
    from olc.models._nested import FieldDefinition

    f = FieldDefinition(
        name="status",
        type="string",
        accepted_values=["used", "failed"],
        value_names={"failed": ["rejected", "not accepted"]},
    )
    assert f.value_names["failed"] == ["rejected", "not accepted"]
    with pytest.raises(ValueError, match="value_names names refunded"):
        FieldDefinition(
            name="status",
            type="string",
            accepted_values=["used"],
            value_names={"refunded": ["returned"]},
        )
    # Without declared values the names stand on their own (the values may be declared upstream).
    assert FieldDefinition(
        name="status", type="string", value_names={"x": ["y"]}
    ).value_names == {"x": ["y"]}
