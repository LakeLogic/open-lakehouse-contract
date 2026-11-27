"""Declared metrics: what a gold table's numbers mean (ontology-metrics-v1, 2026-11-18;
structured metrics, 2026-11-27).

A metric lives on the contract whose table it is computed from, in that contract's ``metrics:``
block, in one of two forms:

* **Parts** (preferred, the common semantic-layer pattern): ``aggregation`` + ``expr`` (+ ``filter``),
  or ``type: ratio`` with a ``numerator`` and ``denominator`` naming two other metrics here.
* **Expression** (fallback): one SQL aggregate (``SUM(gross_revenue_amount)``) or arithmetic over
  other metrics (``Revenue / Trips``).

Never both. :func:`metric_problems` is the ONE definition of a valid block: the strict model,
LakeLogic Core's validation and the platform all call it, so they cannot disagree. For a metric
with parts, :func:`metric_expression` gives its ANSI expression (generated, never stored) and
:func:`metric_sql` the SQL for one platform (needs the ``sql`` extra: sqlglot).

A ratio whose denominator is zero is **no data** (``NULLIF``), never 0.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Literal, Mapping, Optional, Set

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = ["Metric", "metric_problems", "expression_names", "metric_expression", "metric_sql",
           "parts_from_expression", "derived_additivity", "AGGREGATIONS", "DIALECTS"]

Additivity = Literal["additive", "semi_additive", "non_additive"]
Aggregation = Literal["sum", "count", "count_distinct", "avg", "min", "max"]
MetricType = Literal["simple", "ratio"]

AGGREGATIONS = ("sum", "count", "count_distinct", "avg", "min", "max")
#: The platforms an expression must translate to (sqlglot dialect names).
DIALECTS = ("databricks", "tsql", "snowflake", "duckdb")

_PART_KEYS = ("aggregation", "expr", "filter", "numerator", "denominator")


class Metric(BaseModel):
    """One declared metric."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, description="The business name, e.g. `Revenue`.")
    of: Optional[str] = Field(None, description="The business concept it measures, by its ontology name.")
    type: MetricType = Field("simple", description="`simple` (an aggregation) or `ratio` (numerator / denominator).")
    aggregation: Optional[Aggregation] = Field(
        None, description="sum | count | count_distinct | avg | min | max (simple metrics with parts)."
    )
    expr: Optional[str] = Field(
        None, description="What is aggregated: a column, or a row-level expression (`price * quantity`). Never an aggregate."
    )
    filter: Optional[str] = Field(
        None, description="Business state the metric counts (`status = 'completed'`)."
    )
    numerator: Optional[str] = Field(None, description="Ratio: the metric on top, by name.")
    denominator: Optional[str] = Field(None, description="Ratio: the metric below, by name. Zero gives no data.")
    expression: Optional[str] = Field(
        None,
        description="Fallback when the parts cannot say it: an aggregate over this contract's columns "
        "(`SUM(gross_revenue_amount)`), or arithmetic over other metrics (`Revenue / Trips`). Never beside parts.",
    )
    unit: Optional[str] = None
    format: Optional[str] = Field(None, description="Display format for exports, e.g. `#,##0.00` or `0.0%`.")
    additivity: Optional[Additivity] = Field(
        None,
        description="`additive`; `semi_additive` (not summed over time, e.g. a balance); "
        "`non_additive` (a ratio or distinct count). Default: derived from the parts, else additive.",
    )
    description: Optional[str] = None
    also_called: List[str] = Field(
        default_factory=list, description="Other names the business has agreed mean this metric."
    )
    dimensions: List[str] = Field(
        default_factory=list, description="Columns it may be broken down by. Empty: LakeLogic chooses."
    )
    date_column: Optional[str] = Field(None, description="The column its period is read from.")

    @model_validator(mode="after")
    def _one_form(self) -> "Metric":
        problem = _form_problem(self.model_dump())
        if problem:
            raise ValueError(problem)
        return self


def _has_parts(m: Mapping) -> bool:
    return any(m.get(k) not in (None, "") for k in _PART_KEYS) or m.get("type") == "ratio"


def _form_problem(m: Mapping) -> Optional[str]:
    """Why a metric is neither a valid set of parts nor an expression, or ``None``."""
    n = str(m.get("name") or "")
    parts, expression = _has_parts(m), bool(str(m.get("expression") or "").strip())
    if parts and expression:
        return f"metric '{n}' has both parts and an expression; keep one"
    if not parts and not expression:
        return f"metric '{n}' needs parts (aggregation and expr, or a ratio) or an expression"
    if not parts:
        return None
    if m.get("type") == "ratio":
        if not (m.get("numerator") and m.get("denominator")):
            return f"ratio metric '{n}' needs a numerator and a denominator"
        if m.get("aggregation") or m.get("expr"):
            return f"ratio metric '{n}' takes a numerator and denominator, not an aggregation"
        return None
    if m.get("numerator") or m.get("denominator"):
        return f"metric '{n}' has a numerator or denominator but is not type: ratio"
    if not m.get("aggregation"):
        return f"metric '{n}' needs an aggregation (sum, count, count_distinct, avg, min, max)"
    if not str(m.get("expr") or "").strip() and m.get("aggregation") != "count":
        return f"metric '{n}' needs expr: the column it aggregates"
    return None


#: Words an expression may use that are not column names.
_SQL_WORDS = {
    "and", "or", "not", "null", "is", "in", "as", "case", "when", "then", "else", "end", "distinct",
    "true", "false", "between", "like", "over", "partition", "by", "filter", "where", "cast",
    "date", "timestamp", "interval", "int", "integer", "bigint", "double", "float", "decimal",
    "string", "varchar", "boolean",
    # date parts: DATEDIFF(day, a, b), DATE_TRUNC('month', ...), EXTRACT(year FROM ...)
    "year", "quarter", "month", "week", "day", "hour", "minute", "second", "from",
}
_IDENT = re.compile(r"`([^`]+)`|\b([A-Za-z_][A-Za-z0-9_]*)\b(\s*\()?")
_STRING = re.compile(r"'(?:[^']|'')*'")
_AGGREGATE_CALL = re.compile(r"\b(SUM|COUNT|AVG|MIN|MAX)\s*\(", re.I)
_NUMERIC = re.compile(r"int|decimal|numeric|double|float|real|money|number|long|short|byte", re.I)
_TEMPORAL = re.compile(r"date|time", re.I)
_NOT_SUMMABLE = re.compile(r"(rate|ratio|pct|percent|price|unit_cost|score|latitude|longitude)", re.I)
_AMOUNT = re.compile(r"(amount|amt|fare|revenue|price|cost|value|total|sales|fee|tax|paid)", re.I)
_CURRENCY = re.compile(r"^(currency|currency_code|curr|iso_currency|currency_iso)$", re.I)


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


# ── generating SQL from the parts ────────────────────────────────────────────


def metric_expression(metric: Mapping, metrics: Iterable[Mapping] = ()) -> str:
    """The ANSI SQL aggregate a metric stands for: its parts turned into SQL, or its expression.

    ``COUNT(DISTINCT CASE WHEN filter THEN expr END)``; a ratio is ``(numerator) / NULLIF(denominator, 0)``
    so a zero denominator is no data, never 0."""
    if not _has_parts(metric):
        return str(metric.get("expression") or "").strip()
    by_name = {str(m.get("name") or "").strip().lower(): m for m in metrics or [] if isinstance(m, Mapping)}
    if metric.get("type") == "ratio":
        def side(name: str, seen: Set[str]) -> str:
            target = by_name.get(str(name or "").strip().lower())
            if target is None or name.lower() in seen:
                return name
            return f"({_expr_of(target, by_name, seen | {name.lower()})})"
        seen = {str(metric.get("name") or "").lower()}
        return f"{side(metric['numerator'], seen)} / NULLIF({side(metric['denominator'], seen)}, 0)"
    return _simple(metric)


def _expr_of(m: Mapping, by_name: Mapping[str, Mapping], seen: Set[str]) -> str:
    if m.get("type") == "ratio" and _has_parts(m):
        num = by_name.get(str(m.get("numerator") or "").lower())
        den = by_name.get(str(m.get("denominator") or "").lower())
        if num is None or den is None or {str(m.get("numerator")).lower(), str(m.get("denominator")).lower()} & seen:
            return str(m.get("name"))
        return (f"({_expr_of(num, by_name, seen | {str(num.get('name')).lower()})}) / "
                f"NULLIF({_expr_of(den, by_name, seen | {str(den.get('name')).lower()})}, 0)")
    return _simple(m) if _has_parts(m) else str(m.get("expression") or "")


def _simple(m: Mapping) -> str:
    agg = str(m.get("aggregation") or "")
    expr = str(m.get("expr") or "").strip() or "*"
    flt = str(m.get("filter") or "").strip()
    if agg == "count" and expr == "*":
        return f"COUNT(CASE WHEN {flt} THEN 1 END)" if flt else "COUNT(*)"
    inner = f"CASE WHEN {flt} THEN {expr} END" if flt else expr
    if agg == "count_distinct":
        return f"COUNT(DISTINCT {inner})"
    return f"{agg.upper()}({inner})"


def metric_sql(metric: Mapping, dialect: str, metrics: Iterable[Mapping] = ()) -> str:
    """The metric's aggregate in one platform's SQL (``databricks``, ``tsql``, ``snowflake``,
    ``duckdb``...), translated from ANSI by sqlglot. Needs ``pip install open-lakehouse-contract[sql]``."""
    import sqlglot  # optional dependency: the `sql` extra

    return sqlglot.transpile(metric_expression(metric, metrics), read=None, write=dialect)[0]


def parts_from_expression(expression: str, metric_names: Iterable[str] = ()) -> Optional[Dict[str, str]]:
    """The parts an expression is, when it is one of the common shapes; ``None`` otherwise (it
    then stays an expression). Used to offer "Convert" for metrics written before parts existed.

    ``SUM(x)`` / ``COUNT(*)`` / ``COUNT(DISTINCT x)`` / ``AGG(CASE WHEN f THEN x END)`` and
    ``A / B`` or ``A / NULLIF(B, 0)`` over two declared metrics. Needs the ``sql`` extra."""
    text = str(expression or "").strip()
    names = {n.strip().lower(): n.strip() for n in metric_names or () if n and n.strip()}
    ratio = re.fullmatch(r"\(?\s*(.+?)\s*\)?\s*/\s*(?:NULLIF\s*\(\s*)?\(?\s*(.+?)\s*\)?(?:\s*,\s*0\s*\))?", text, re.I)
    if ratio and ratio.group(1).lower() in names and ratio.group(2).lower() in names:
        return {"type": "ratio", "numerator": names[ratio.group(1).lower()], "denominator": names[ratio.group(2).lower()]}
    try:
        import sqlglot
        from sqlglot import exp
    except ImportError:
        return None
    try:
        tree = sqlglot.parse_one(text)
    except Exception:  # noqa: BLE001 - not SQL: stays an expression
        return None
    kinds = {exp.Sum: "sum", exp.Avg: "avg", exp.Min: "min", exp.Max: "max", exp.Count: "count"}
    agg = next((v for k, v in kinds.items() if type(tree) is k), None)
    if agg is None:
        return None
    arg = tree.this
    if isinstance(arg, exp.Distinct):
        if agg != "count" or len(arg.expressions) != 1:
            return None
        agg, arg = "count_distinct", arg.expressions[0]
    if isinstance(arg, exp.Star):
        return {"aggregation": "count"} if agg == "count" else None
    out: Dict[str, str] = {"aggregation": agg}
    if isinstance(arg, exp.Case):
        ifs = arg.args.get("ifs") or []
        default = arg.args.get("default")
        if len(ifs) != 1 or (default is not None and not (agg == "sum" and default.sql() == "0")):
            return None
        out["filter"] = ifs[0].this.sql()
        arg = ifs[0].args["true"]
        if agg == "count" and isinstance(arg, exp.Literal):
            return out  # COUNT(CASE WHEN f THEN 1 END): a filtered row count
    if arg.find(exp.AggFunc):
        return None
    out["expr"] = arg.sql()
    return out


def _untranslatable(text: str) -> Optional[str]:
    """Why ``text`` does not parse or translate to every platform; ``None`` when it does, or when
    sqlglot is not installed (the check then runs where it is: Core and the platform)."""
    try:
        import sqlglot
        from sqlglot.errors import ErrorLevel
    except ImportError:
        return None
    try:
        tree = sqlglot.parse_one(text, error_level=ErrorLevel.RAISE)
    except Exception as exc:  # noqa: BLE001 - any parse error is the reason
        return f"does not parse ({str(exc).splitlines()[0][:120]})"
    for d in DIALECTS:
        try:
            tree.sql(dialect=d, unsupported_level=ErrorLevel.RAISE)
        except Exception:  # noqa: BLE001
            return f"does not translate to {d}"
    return None


# ── the rule ─────────────────────────────────────────────────────────────────


def derived_additivity(metric: Mapping, keys: Iterable[str] = ()) -> Optional[str]:
    """What the parts say about adding up; ``None`` when they cannot say (an expression)."""
    if not _has_parts(metric):
        return None
    if metric.get("type") == "ratio":
        return "non_additive"
    agg = metric.get("aggregation")
    if agg in ("sum", "count"):
        return "additive"
    if agg == "count_distinct":
        key = [k.lower() for k in keys or ()]
        return "additive" if len(key) == 1 and str(metric.get("expr") or "").strip("`\" ").lower() == key[0] else "non_additive"
    return "non_additive"  # avg, min, max


def metric_problems(
    metrics: Iterable[Dict],
    field_names: Iterable[str],
    *,
    field_types: Optional[Mapping[str, str]] = None,
    keys: Iterable[str] = (),
    references: Iterable[str] = (),
) -> List[str]:
    """Every problem with a ``metrics:`` block, each naming the metric and the missing name.

    Always: names unique; one form (parts or expression); every column named is a field; every
    metric named (in an expression, numerator or denominator) is declared here; no metric refers
    to itself; ``expr`` is not an aggregate; declared additivity agrees with the parts.
    When sqlglot is installed: ``expr``, ``filter`` and ``expression`` translate to every platform.
    When ``field_types`` / ``keys`` / ``references`` are given: no sum or average of a key, a
    dimension reference, a date or text; no sum of a rate or price; no plain sum of an amount on
    a table that also holds a currency column, unless broken down by it."""
    items = [m for m in metrics or [] if isinstance(m, dict)]
    fields = set(field_names or [])
    lower_fields = {f.lower(): f for f in fields}
    types = {str(k).lower(): str(v or "") for k, v in (field_types or {}).items()}
    key_set = {str(k).lower() for k in keys or ()}
    ref_set = {str(r).lower() for r in references or ()}
    currency = next((f for f in fields if _CURRENCY.match(f)), None)
    names = [str(m.get("name") or "").strip() for m in items]
    problems: List[str] = []
    seen: Set[str] = set()
    for n in names:
        if n.lower() in seen:
            problems.append(f"metric '{n}' is declared more than once")
        seen.add(n.lower())
    declared = {n.lower(): n for n in names if n}
    refs: Dict[str, Set[str]] = {}
    for m, n in zip(items, names):
        form = _form_problem(m)
        if form:
            problems.append(form)
            refs[n] = set()
            continue
        if _has_parts(m):
            used: Set[str] = set()
            if m.get("type") == "ratio":
                for side in ("numerator", "denominator"):
                    target = str(m.get(side) or "").strip()
                    if target.lower() not in declared:
                        problems.append(f"metric '{n}' has {side} '{target}', which is not a metric of this contract")
                    else:
                        used.add(declared[target.lower()])
            else:
                expr = str(m.get("expr") or "")
                if _AGGREGATE_CALL.search(_STRING.sub(" ", expr)):
                    problems.append(f"metric '{n}' has an aggregate in expr; put the aggregation in 'aggregation'")
                cols: Set[str] = set()
                for text in (expr, str(m.get("filter") or "")):
                    cols |= expression_names(text, [], fields)[1]
                for col in sorted(c for c in cols if c not in fields):
                    problems.append(f"metric '{n}' names column '{col}', which is not a field of this contract")
                for label, text in (("expr", expr), ("filter", str(m.get("filter") or ""))):
                    reason = _untranslatable(text) if text.strip() else None
                    if reason:
                        problems.append(f"metric '{n}' {label} {reason}")
                problems += _aggregation_problems(n, m, types, key_set, ref_set, currency)
            refs[n] = used
        else:
            used, columns = expression_names(str(m.get("expression") or ""), [x for x in names if x and x != n] + [n], fields)
            refs[n] = used
            for col in sorted(columns - fields):
                problems.append(f"metric '{n}' names column '{col}', which is not a field of this contract")
            if not used:  # arithmetic over metrics names metrics, not SQL a platform runs directly
                reason = _untranslatable(str(m.get("expression") or ""))
                if reason:
                    problems.append(f"metric '{n}' expression {reason}")
        derived = derived_additivity(m, keys)
        if derived and m.get("additivity") == "additive" and derived == "non_additive":
            problems.append(f"metric '{n}' is declared additive, but a {m.get('aggregation') or 'ratio'} does not add up")
        for col in m.get("dimensions") or []:
            if col not in fields:
                problems.append(f"metric '{n}' lists dimension '{col}', which is not a field of this contract")
        if m.get("date_column") and m["date_column"] not in fields:
            problems.append(f"metric '{n}' has date_column '{m['date_column']}', which is not a field of this contract")
    del lower_fields

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


def _aggregation_problems(n: str, m: Mapping, types: Mapping[str, str], keys: Set[str], refs: Set[str],
                          currency: Optional[str]) -> List[str]:
    agg = m.get("aggregation")
    expr = str(m.get("expr") or "").strip().strip("`\"")
    col = expr.lower()
    if agg not in ("sum", "avg") or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", expr):
        return []
    typ = types.get(col)
    out: List[str] = []
    if col in keys or col in refs:
        out.append(f"metric '{n}' takes {agg} of '{expr}', a key; count it instead")
    elif typ is not None and (_TEMPORAL.search(typ) or (typ and not _NUMERIC.search(typ))):
        out.append(f"metric '{n}' takes {agg} of '{expr}', which is not a number ({typ})")
    elif agg == "sum" and _NOT_SUMMABLE.search(expr):
        out.append(f"metric '{n}' sums '{expr}', a rate or price; average it or sum the amount instead")
    elif (agg == "sum" and currency and _AMOUNT.search(expr)
          and currency not in (m.get("dimensions") or [])):
        out.append(f"metric '{n}' sums '{expr}' across currencies; add '{currency}' to its dimensions")
    return out
