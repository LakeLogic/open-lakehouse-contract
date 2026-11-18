"""Declared metrics: what a gold table's numbers mean (ontology-metrics-v1, 2026-11-18).

A metric lives on the gold contract whose table it is computed from, in that contract's
``metrics:`` block. Base metrics aggregate columns (``SUM(gross_revenue_amount)``); derived metrics
combine other metrics on the same contract (``Revenue / Trips``). :func:`metric_problems` is the
ONE definition of a valid block: the strict model, LakeLogic Core's validation and the platform
all call it, so they cannot disagree on what is accepted.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Literal, Optional, Set

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["Metric", "metric_problems", "expression_names"]

Additivity = Literal["additive", "semi_additive", "non_additive"]


class Metric(BaseModel):
    """One declared metric on a gold contract."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, description="The business name, e.g. `Revenue`.")
    of: Optional[str] = Field(None, description="The business concept it measures, by its ontology name.")
    expression: str = Field(
        ...,
        min_length=1,
        description="An aggregate over this contract's columns (`SUM(gross_revenue_amount)`), or "
        "arithmetic over other metrics on this contract (`Revenue / Trips`).",
    )
    unit: Optional[str] = None
    additivity: Additivity = Field(
        "additive",
        description="`additive`; `semi_additive` (not summed over time, e.g. a balance); "
        "`non_additive` (a ratio or distinct count, never summed).",
    )
    description: Optional[str] = None
    also_called: List[str] = Field(
        default_factory=list, description="Other names the business has agreed mean this metric."
    )
    dimensions: List[str] = Field(
        default_factory=list, description="Columns it may be broken down by. Empty: LakeLogic chooses."
    )
    date_column: Optional[str] = Field(None, description="The column its period is read from.")


#: Words an expression may use that are not column names.
_SQL_WORDS = {
    "and", "or", "not", "null", "is", "in", "as", "case", "when", "then", "else", "end", "distinct",
    "true", "false", "between", "like", "over", "partition", "by", "filter", "where", "cast",
    "date", "timestamp", "interval", "int", "integer", "bigint", "double", "float", "decimal",
    "string", "varchar", "boolean",
}
_IDENT = re.compile(r"`([^`]+)`|\b([A-Za-z_][A-Za-z0-9_]*)\b(\s*\()?")
_STRING = re.compile(r"'(?:[^']|'')*'")


def expression_names(
    expression: str, metric_names: Iterable[str], field_names: Iterable[str] = ()
) -> tuple[Set[str], Set[str]]:
    """The metrics and the columns an expression names: ``(metrics, columns)``.

    Metric names may contain spaces, so they are matched first, longest first, case-insensitively.
    A metric named like one of the contract's columns ("Fare" over ``fare``) is read as the column:
    ``SUM(fare)`` aggregates the column, it does not refer to the metric. What remains: identifiers
    that are not functions (followed by ``(``) or SQL words are columns."""
    text = _STRING.sub(" ", expression or "")
    used: Set[str] = set()
    columns_lower = {f.lower() for f in field_names or () if f}
    for name in sorted({n for n in metric_names if n and n.lower() not in columns_lower}, key=len, reverse=True):
        pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", re.I)
        if pattern.search(text):
            used.add(name)
            text = pattern.sub(" ", text)
    columns: Set[str] = set()
    for quoted, bare, call in _IDENT.findall(text):
        word = quoted or bare
        if not word or call or (not quoted and word.lower() in _SQL_WORDS):
            continue
        columns.add(word)
    return used, columns


def metric_problems(metrics: Iterable[Dict], field_names: Iterable[str]) -> List[str]:
    """Every problem with a ``metrics:`` block, each naming the metric and the missing name.

    Checks: names are unique; every column an expression names is a field of this contract; every
    metric it names is declared here; no metric refers to itself, directly or through another."""
    items = [m for m in metrics or [] if isinstance(m, dict)]
    fields = set(field_names or [])
    names = [str(m.get("name") or "").strip() for m in items]
    problems: List[str] = []
    seen: Set[str] = set()
    for n in names:
        if n.lower() in seen:
            problems.append(f"metric '{n}' is declared more than once")
        seen.add(n.lower())
    refs: Dict[str, Set[str]] = {}
    for m, n in zip(items, names):
        used, columns = expression_names(str(m.get("expression") or ""), [x for x in names if x and x != n] + [n], fields)
        refs[n] = used
        for col in sorted(columns - fields):
            problems.append(f"metric '{n}' names column '{col}', which is not a field of this contract")
        for key in ("dimensions",):
            for col in m.get(key) or []:
                if col not in fields:
                    problems.append(f"metric '{n}' lists dimension '{col}', which is not a field of this contract")
        if m.get("date_column") and m["date_column"] not in fields:
            problems.append(f"metric '{n}' has date_column '{m['date_column']}', which is not a field of this contract")

    def cycle(start: str) -> Optional[List[str]]:
        stack = [(start, [start])]
        while stack:
            node, path = stack.pop()
            for nxt in refs.get(node, ()):
                if nxt == start:
                    return path + [start]
                if nxt not in path:
                    stack.append((nxt, path + [nxt]))
        return None

    reported: Set[frozenset] = set()
    for n in names:
        path = cycle(n)
        if path and frozenset(path) not in reported:
            reported.add(frozenset(path))
            problems.append(
                f"metric '{n}' refers to itself" if len(path) == 2
                else f"metric '{n}' refers to itself through {' -> '.join(path[1:-1])}"
            )
    return problems
