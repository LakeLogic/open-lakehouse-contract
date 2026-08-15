"""Runtime adapters: run a conformance case on a specific LakeLogic engine.

An adapter is a thin wrapper over ``lakelogic.DataProcessor`` that turns a
:class:`ConformanceCase` into a normalisable :class:`ExecutionResult`. The core
insight the harness proves: the SAME case, run through different engines, yields
the SAME normalised outcome.
"""
from __future__ import annotations

import re
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Protocol

from .model import ConformanceCase, ExecutionError, ExecutionResult

_RULE_RE = re.compile(r"Rule failed:\s*(\S+)")


class ConformanceAdapter(Protocol):
    name: str
    capabilities: set[str]

    def execute(self, case: ConformanceCase) -> ExecutionResult: ...


def _model_fields(contract: dict) -> list[str]:
    fields = (contract.get("model") or {}).get("fields") or []
    return [f["name"] for f in fields if isinstance(f, dict) and "name" in f]


def _project(rows: list[dict], cols: list[str]) -> list[dict]:
    """Keep only declared model columns (drop lineage/meta like _lakelogic_*)."""
    if not cols:
        return [dict(r) for r in rows]
    return [{c: r.get(c) for c in cols if c in r} for r in rows]


def _failed_rules(bad_rows: list[dict]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in bad_rows:
        errors = row.get("_lakelogic_errors") or []
        if isinstance(errors, str):
            errors = [errors]
        for err in errors:
            for match in _RULE_RE.finditer(str(err)):
                counter[match.group(1)] += 1
    return dict(counter)


class LakeLogicAdapter:
    """Shared implementation; subclasses just pick the engine + capabilities."""

    engine: str = ""
    name: str = ""
    capabilities: set[str] = set()
    # Run cases through the STRICT contract path (gate on OLCContractV1), so a case
    # whose contract isn't a valid canonical OLC contract fails instead of silently
    # slipping through the lenient runtime. The corpus is also strict-checked
    # directly (test_all_case_contracts_are_strict_valid) as a belt-and-braces guard.
    strict: bool = True

    def _make_processor(self, DataProcessor, case: ConformanceCase):
        return DataProcessor(engine=self.engine, contract=dict(case.contract), strict=self.strict)

    def execute(self, case: ConformanceCase) -> ExecutionResult:
        import polars as pl

        from lakelogic import DataProcessor

        cols = _model_fields(case.contract)
        input_df = pl.DataFrame(case.input_rows) if case.input_rows else pl.DataFrame()

        try:
            if case.is_materialization:
                return self._execute_materialization(case, input_df, cols, pl, DataProcessor)
            processor = self._make_processor(DataProcessor, case)
            good, bad = processor.run(input_df)
            good_rows = good.to_dicts()
            bad_rows = bad.to_dicts()
            return ExecutionResult(
                accepted=_project(good_rows, cols),
                quarantined=_project(bad_rows, cols),
                run_metadata=self._metadata(processor, good_rows, bad_rows, materialized=False),
            )
        except Exception as exc:  # engine-neutral surface
            return ExecutionResult(
                accepted=[],
                quarantined=[],
                run_metadata={},
                exception=ExecutionError(
                    category="execution_error",
                    code="OLC_EXECUTION_ERROR",
                    message=str(exc)[:200],
                ),
            )

    def _execute_materialization(self, case, input_df, cols, pl, DataProcessor) -> ExecutionResult:
        mat = case.materialization
        tmp = Path(tempfile.mkdtemp()) / case.id.replace(".", "_")
        target = str(tmp)

        # Seed prior target state (if any) so merge/append has something to act on.
        if mat.seed:
            seed_rows = _read_jsonl(case.directory / mat.seed)
            if seed_rows:
                seeder = self._make_processor(DataProcessor, case)
                seeder.run(pl.DataFrame(seed_rows), materialize=True, materialize_target=target)

        processor = self._make_processor(DataProcessor, case)
        good, bad = processor.run(input_df, materialize=True, materialize_target=target)
        target_rows = self._read_target(target, mat.format, cols)

        if mat.idempotent:
            # Re-run the identical merge; the target must not change.
            again = self._make_processor(DataProcessor, case)
            again.run(input_df, materialize=True, materialize_target=target)
            target_rows_2 = self._read_target(target, mat.format, cols)
            # Stash the second read so the comparator can assert stability.
            meta_extra = {"idempotent_target_rows": target_rows_2}
        else:
            meta_extra = {}

        meta = self._metadata(processor, good.to_dicts(), bad.to_dicts(), materialized=True)
        meta.update(meta_extra)
        return ExecutionResult(
            accepted=_project(good.to_dicts(), cols),
            quarantined=_project(bad.to_dicts(), cols),
            run_metadata=meta,
            target_rows=target_rows,
        )

    @staticmethod
    def _read_target(target: str, fmt: str, cols: list[str]) -> list[dict]:
        import polars as pl

        if fmt == "delta":
            from deltalake import DeltaTable

            table = pl.from_arrow(DeltaTable(target).to_pyarrow_table())
        else:  # parquet / other columnar file
            table = pl.read_parquet(target)
        return _project(table.to_dicts(), cols)

    @staticmethod
    def _metadata(processor, good_rows, bad_rows, *, materialized: bool) -> dict:
        report = getattr(processor, "last_report", None) or {}
        counts = report.get("counts") or {}
        accepted = len(good_rows)
        quarantined = len(bad_rows)
        dataset_failed = [
            r.get("name")
            for r in (report.get("dataset_rules") or [])
            if isinstance(r, dict) and r.get("passed") is False
        ]
        return {
            "contract_version": report.get("contract_version"),
            "status": "completed_with_quarantine" if quarantined else "completed",
            "rows_input": counts.get("source", counts.get("total", accepted + quarantined)),
            "rows_accepted": accepted,
            "rows_quarantined": quarantined,
            "failed_rules": _failed_rules(bad_rows),
            "dataset_rules_failed": dataset_failed,
            "materialized": materialized,
        }


def _read_jsonl(path: Path) -> list[dict]:
    import json

    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


class DuckDBAdapter(LakeLogicAdapter):
    engine = "duckdb"
    name = "duckdb"
    capabilities = {
        "quality.row.sql",
        "quality.row.regex",
        "quality.dataset.unique",
        "quarantine.attribution",
        "transformations.pre",
        "transformations.post",
        "transformations.filter",
        "transformations.deduplicate_by_latest",
        "materialization.merge",
    }


class PolarsAdapter(LakeLogicAdapter):
    engine = "polars"
    name = "polars"
    capabilities = {
        "quality.row.sql",
        "quality.row.regex",
        "quality.dataset.unique",
        "quarantine.attribution",
        "transformations.pre",
        "transformations.post",
        "transformations.filter",
        "transformations.deduplicate_by_latest",
        "materialization.merge",
    }


ADAPTERS: dict[str, type[LakeLogicAdapter]] = {
    "duckdb": DuckDBAdapter,
    "polars": PolarsAdapter,
}
