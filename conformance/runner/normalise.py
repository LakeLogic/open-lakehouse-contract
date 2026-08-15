"""Normalise engine output to a comparable semantic form.

We compare *semantic outcomes*, not physical representations. Engines differ in
row/column order, int-vs-float encoding, decimal precision, generated run IDs,
timestamps and error text. Normalisation strips all of that so DuckDB, Polars,
Spark, etc. can be held to the same authored expectations.
"""
from __future__ import annotations

from typing import Any


def _round_numbers(value: Any, tolerance: float) -> Any:
    """Collapse int/float representation and clamp precision to the tolerance."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if tolerance and tolerance > 0:
            # Snap to the tolerance grid so 1 == 1.0 == 0.9999996.
            digits = max(0, -int(round(__import__("math").log10(tolerance))))
            return round(float(value), digits)
        return float(value)
    return value


def normalise_rows(
    rows: list[dict],
    *,
    sort_by: list[str] | None = None,
    ignore_fields: set[str] | None = None,
    numeric_tolerance: float = 1e-6,
) -> list[dict]:
    """Return a canonical, order-independent view of ``rows``.

    - drops ``ignore_fields`` (run IDs, timestamps, durations, catalog names);
    - normalises numeric representation to ``numeric_tolerance``;
    - sorts columns within each row, then sorts the row list deterministically.
    """
    ignore = ignore_fields or set()
    out: list[dict] = []
    for row in rows:
        clean = {
            k: _round_numbers(v, numeric_tolerance)
            for k, v in row.items()
            if k not in ignore
        }
        # column order is not semantic — canonicalise it
        out.append(dict(sorted(clean.items())))

    keys = sort_by or None

    def sort_key(row: dict):
        if keys:
            return tuple(_stringify(row.get(k)) for k in keys)
        # no explicit key: sort by the whole row's items
        return tuple(_stringify(v) for _, v in sorted(row.items()))

    return sorted(out, key=sort_key)


def _stringify(value: Any) -> str:
    """Total, type-stable ordering key (None sorts first, consistently)."""
    if value is None:
        return "\x00"
    return f"{type(value).__name__}:{value}"
