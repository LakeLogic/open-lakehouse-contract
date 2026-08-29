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
from typing import Protocol

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
        contract = self._contract_with_references(case)
        return DataProcessor(
            engine=self.engine, contract=dict(contract), strict=self.strict
        )

    def _contract_with_references(self, case: ConformanceCase) -> dict:
        """Materialise each link's reference data (references/<name>.jsonl -> a temp
        parquet) and point ``link.path`` at it, so join/lookup transforms have a real
        reference table to resolve against — engine-neutral (both read parquet).
        """
        contract = dict(case.contract)

        # external_logic: anchor the script path to the case dir (the runtime gets
        # a dict contract with no _base_path, so a relative path can't resolve), and
        # align the pinned engine with the engine under test — the step runs on the
        # pipeline engine, and the required `engine` field must reflect that.
        ext = contract.get("external_logic")
        if ext:
            ext = dict(ext)
            p = ext.get("path")
            if p and not Path(p).is_absolute():
                ext["path"] = str((case.directory / p).resolve())
            ext["engine"] = self.engine
            contract["external_logic"] = ext

        links = contract.get("links")
        if not links:
            return contract
        import tempfile

        import polars as pl

        ref_dir = case.directory / "references"
        resolved = []
        for link in links:
            link = dict(link)
            name = link.get("name")
            ref_jsonl = ref_dir / f"{name}.jsonl" if name else None
            if ref_jsonl and ref_jsonl.exists():
                rows = _read_jsonl(ref_jsonl)
                tmp = Path(tempfile.mkdtemp()) / f"{name}.parquet"
                pl.DataFrame(rows).write_parquet(tmp)
                link["path"] = str(tmp)
            resolved.append(link)
        contract["links"] = resolved
        return contract

    # ── frame in/out (overridden by non-polars engines like Spark) ────────────
    def _to_frame(self, rows: list[dict]):
        import polars as pl

        return pl.DataFrame(rows) if rows else pl.DataFrame()

    def _to_rows(self, frame) -> list[dict]:
        return frame.to_dicts()

    def _materialise_source(self, case: ConformanceCase) -> str:
        """Write the case input to a real parquet file for ``input_via: source``.

        The read path is where ``source.flatten_nested`` (and anything else applied
        while loading) actually runs. ``run()`` takes an already-loaded frame and so
        skips it entirely — which is why those behaviours were untestable here.

        Parquet, not JSONL: every engine reads it natively, so the case measures the
        runtime rather than a text parser. Values are written as authored, so a JSON
        *string* column stays a string — that is the input flatten_nested exists for.
        """
        import polars as pl

        path = Path(tempfile.mkdtemp()) / "source.parquet"
        pl.DataFrame(case.input_rows).write_parquet(path)
        return str(path)

    def execute(self, case: ConformanceCase) -> ExecutionResult:
        import polars as pl
        from lakelogic import DataProcessor

        cols = _model_fields(case.contract)
        input_df = self._to_frame(case.input_rows)

        try:
            if case.is_materialization:
                return self._execute_materialization(
                    case, input_df, cols, pl, DataProcessor
                )
            processor = self._make_processor(DataProcessor, case)
            if case.reads_from_source:
                good, bad = processor.run_source(self._materialise_source(case))
            else:
                good, bad = processor.run(input_df)
            good_rows = self._to_rows(good)
            bad_rows = self._to_rows(bad)
            return ExecutionResult(
                accepted=_project(good_rows, cols),
                quarantined=_project(bad_rows, cols),
                run_metadata=self._metadata(
                    processor, good_rows, bad_rows, materialized=False
                ),
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

    def _execute_materialization(
        self, case, input_df, cols, pl, DataProcessor
    ) -> ExecutionResult:
        mat = case.materialization
        tmp = Path(tempfile.mkdtemp()) / case.id.replace(".", "_")
        target = str(tmp)

        # Seed prior target state (if any) so merge/append has something to act on.
        if mat.seed:
            seed_rows = _read_jsonl(case.directory / mat.seed)
            if seed_rows:
                seeder = self._make_processor(DataProcessor, case)
                seeder.run(
                    self._to_frame(seed_rows),
                    materialize=True,
                    materialize_target=target,
                )

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

        meta = self._metadata(
            processor, self._to_rows(good), self._to_rows(bad), materialized=True
        )
        meta.update(meta_extra)
        return ExecutionResult(
            accepted=_project(self._to_rows(good), cols),
            quarantined=_project(self._to_rows(bad), cols),
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
            "rows_input": counts.get(
                "source", counts.get("total", accepted + quarantined)
            ),
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
        "transformations.deduplicate",
        "transformations.deduplicate_by_latest",  # deprecated shorthand
        "transformations.lower",
        "transformations.trim",
        "transformations.cast",
        "transformations.coalesce",
        "transformations.select",
        "transformations.drop",
        "transformations.map_values",
        "transformations.json_extract",
        "transformations.split",
        "transformations.date_diff",
        "transformations.bucket",
        "transformations.lookup",
        "transformations.join",
        "transformations.explode",
        "transformations.date_range_explode",
        "materialization.merge",
        "materialization.scd2",
        "external_logic.multi_frame_links",
        "external_logic.deterministic_extraction",
        "extraction.regex",
        # Nested/complex column types (struct, array) carried through the model.
        "model.nested_types",
        # Read-path JSON-string expansion (source.flatten_nested).
        "source.flatten_nested",
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
        "transformations.deduplicate",
        "transformations.deduplicate_by_latest",  # deprecated shorthand
        "transformations.lower",
        "transformations.trim",
        "transformations.cast",
        "transformations.coalesce",
        "transformations.select",
        "transformations.drop",
        "transformations.map_values",
        "transformations.json_extract",
        "transformations.split",
        "transformations.date_diff",
        "transformations.bucket",
        "transformations.lookup",
        "transformations.join",
        "transformations.explode",
        "transformations.date_range_explode",
        "materialization.merge",
        "materialization.scd2",
        "external_logic.multi_frame_links",
        "external_logic.deterministic_extraction",
        "extraction.regex",
        # Nested/complex column types (struct, array) carried through the model.
        "model.nested_types",
        # Read-path JSON-string expansion (source.flatten_nested).
        "source.flatten_nested",
    }


class SparkAdapter(LakeLogicAdapter):
    """Optional third engine — opt in via OLC_CONFORMANCE_SPARK=1 or
    OLC_CONFORMANCE_ENGINES=...,spark (Spark's JVM startup makes it slow, so it is
    off by default). Declares the same capability set as the others so the whole
    corpus is exercised on Spark and any divergence is surfaced.
    """

    engine = "spark"
    name = "spark"
    capabilities = set(PolarsAdapter.capabilities)

    _spark = None  # cached session (JVM startup is expensive)

    @classmethod
    def _session(cls):
        if cls._spark is None:
            from pyspark.sql import SparkSession

            # Give this PROCESS its own warehouse and Derby metastore.
            #
            # Without it, every local Spark session in the same working directory
            # shares ./spark-warehouse and ./metastore_db — and Derby allows a
            # single writer. Two conformance runs at once (a full sweep plus a
            # targeted -k re-run, say) then fight over the metastore and cases fail
            # for reasons that have nothing to do with the engine or the corpus.
            # That is a nasty failure to debug precisely because it looks like a
            # real regression: the cases that lose the race are the Delta ones
            # (SCD2, merge, materialisation), and they pass again in isolation.
            spark_home = Path(tempfile.mkdtemp(prefix="olc-spark-"))
            derby_home = spark_home / "derby"
            derby_home.mkdir(parents=True, exist_ok=True)

            builder = (
                SparkSession.builder.master("local[2]")
                .appName("olc-conformance")
                .config("spark.sql.warehouse.dir", str(spark_home / "warehouse"))
                .config(
                    "spark.driver.extraJavaOptions",
                    f"-Dderby.system.home={derby_home}",
                )
                # Delta extension so merge/SCD2 materialisation works (as it does on
                # a real Databricks/Delta cluster).
                .config(
                    "spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension"
                )
                .config(
                    "spark.sql.catalog.spark_catalog",
                    "org.apache.spark.sql.delta.catalog.DeltaCatalog",
                )
            )
            try:
                from delta import configure_spark_with_delta_pip

                builder = configure_spark_with_delta_pip(builder)
            except Exception:  # pragma: no cover - delta-spark not installed
                pass
            cls._spark = builder.getOrCreate()
            cls._spark.sparkContext.setLogLevel("ERROR")
        return cls._spark

    def _isession(self):
        """A per-case Spark session (``newSession``) that shares the JVM/cluster but
        ISOLATES temp views and the SQL catalog. Engine code names temp views by
        ``id(self)``, which Python recycles after GC — so across a long shared-session
        suite run two cases could collide on a view name and, under lazy evaluation,
        read each other's data (the intermittent dedup 3-rows-vs-2 symptom). A fresh
        session per case makes view namespaces disjoint and the run deterministic."""
        s = getattr(self, "_inst_session", None)
        if s is None:
            s = self._session().newSession()
            self._inst_session = s
        return s

    def _to_frame(self, rows: list[dict]):
        if not rows:
            return self._isession().createDataFrame([], schema="_empty STRING")
        from pyspark.sql.types import (
            ArrayType,
            BooleanType,
            DoubleType,
            LongType,
            StringType,
            StructField,
            StructType,
        )

        # Build an explicit schema — Spark can't infer an all-null column (e.g. a
        # coalesce/lookup input where a source is entirely null).
        def _infer_value(v):
            """Spark type for a single JSON value.

            Dicts become a real StructType (not a stringified Map): a case about
            nested types must hand Spark an actual struct column, otherwise the
            adapter — not the engine — is what the case measures.
            """
            if isinstance(v, bool):
                return BooleanType()
            if isinstance(v, int):
                return LongType()
            if isinstance(v, float):
                return DoubleType()
            if isinstance(v, dict):
                return StructType(
                    [StructField(k, _infer_value(x), True) for k, x in v.items()]
                )
            if isinstance(v, list):
                for item in v:
                    if item is not None:
                        return ArrayType(_infer_value(item))
                return ArrayType(StringType())
            return StringType()

        def _infer(col: str):
            for r in rows:
                v = r.get(col)
                if v is None:
                    continue
                return _infer_value(v)
            return StringType()  # all-null -> string

        cols = list(rows[0].keys())
        schema = StructType([StructField(c, _infer(c), True) for c in cols])
        return self._isession().createDataFrame(rows, schema=schema)

    def _to_rows(self, frame) -> list[dict]:
        import math

        from pyspark.sql import Row

        def _plain(v):
            """Physical Spark containers -> plain Python, so a struct column compares
            against the authored JSONL. A pyspark ``Row`` is not a dict, so without
            this a correctly-preserved struct looks like a mismatch — a harness
            artefact, not an engine defect."""
            if isinstance(v, Row):
                return {k: _plain(x) for k, x in v.asDict(recursive=False).items()}
            if isinstance(v, dict):
                return {k: _plain(x) for k, x in v.items()}
            if isinstance(v, (list, tuple)):
                return [_plain(x) for x in v]
            # pandas represents SQL NULL as NaN — restore None so comparisons match.
            if isinstance(v, float) and math.isnan(v):
                return None
            return v

        records = frame.toPandas().to_dict("records")
        return [{k: _plain(v) for k, v in rec.items()} for rec in records]


_ADAPTER_REGISTRY: dict[str, type[LakeLogicAdapter]] = {
    "duckdb": DuckDBAdapter,
    "polars": PolarsAdapter,
    "spark": SparkAdapter,
}


def _enabled_adapter_names() -> list[str]:
    """Which engines the conformance run uses. DuckDB + Polars by default; Spark is
    opt-in via OLC_CONFORMANCE_SPARK=1 or an explicit OLC_CONFORMANCE_ENGINES list."""
    import os

    explicit = os.environ.get("OLC_CONFORMANCE_ENGINES")
    if explicit:
        names = [n.strip().lower() for n in explicit.split(",") if n.strip()]
    elif os.environ.get("OLC_CONFORMANCE_SPARK") == "1":
        names = ["duckdb", "polars", "spark"]
    else:
        names = ["duckdb", "polars"]
    return [n for n in names if n in _ADAPTER_REGISTRY]


ADAPTERS: dict[str, type[LakeLogicAdapter]] = {
    n: _ADAPTER_REGISTRY[n] for n in _enabled_adapter_names()
}
