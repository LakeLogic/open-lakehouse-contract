"""Executable-conformance suite: core cases must PASS on every core adapter.

The whole point of the harness: the SAME behavioural case, run through DuckDB and
Polars, produces the SAME normalised outcome. A case is authored once (contract +
input + expected accepted/quarantined/target); each adapter must reproduce it.

Two run modes:

* **local / soft** (default) — if the LakeLogic runtime or an optional dependency
  (deltalake) isn't installed, the affected tests skip so a docs-only checkout still
  collects.
* **CI / strict** — set ``OLC_CONFORMANCE_REQUIRE=1``. Missing runtime/dependencies
  become hard FAILURES, and any SKIP fails the suite. This is what the dedicated CI
  job runs so a broken DuckDB/Polars implementation cannot merge green.

Conformance discipline:
* For **required levels** (core-runtime, materialization) a case MUST reach ``PASS``.
  ``UNSUPPORTED`` is a FAILURE there — an unimplemented core feature is not success.
* ``UNSUPPORTED`` is only acceptable for optional/higher levels, and is surfaced in
  a separate capability matrix (``test_capability_matrix``), never as silent success.
"""
# ruff: noqa: E402 — the imports below are intentionally deferred past the _require()
# dependency guards, so a docs-only checkout without the runtime still collects.

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

CONF = Path(__file__).resolve().parent
sys.path.insert(0, str(CONF))

# In CI (strict mode) the whole point is to run against the real runtime, so a
# missing import is a hard failure, not a skip.
REQUIRE = os.environ.get("OLC_CONFORMANCE_REQUIRE") == "1"

# Levels where a case must genuinely PASS (UNSUPPORTED/SKIP are failures).
REQUIRED_LEVELS = {"core-runtime", "materialization"}


def _require(module: str, reason: str):
    """Hard-import in strict/CI mode; soft skip locally."""
    if REQUIRE:
        __import__(module)
        return
    pytest.importorskip(module, reason=reason)


_require("runner", "conformance runner import failed")
_require("lakelogic", "LakeLogic runtime not installed")  # engines run the cases
_require("olc.models", "public OLC strict model unavailable (pip install .[models])")
_require("polars", "polars not installed")

from runner import load_all_cases, run_case
from runner.adapters import ADAPTERS
from runner.harness import PASS, UNSUPPORTED

CASES = load_all_cases()
ADAPTER_NAMES = list(ADAPTERS)

# Known cross-engine gaps this corpus has surfaced — real runtime defects, tracked
# here rather than papered over. strict xfail: the day the engine is fixed, the
# xpass fails this test and prompts removing the entry. Never turn a FAIL into PASS.
#
# Each entry names the ACTUAL wrong behaviour and where it lives, so the entry is a
# bug report rather than a mute. A gap is not the same as a disagreement about
# mechanism: where the spec genuinely permits more than one enforcement, that
# belongs in the case (see OLC-N-004's `refusal_conforms`), NOT here — otherwise an
# engine gets recorded as deviant for being stricter than its peers.
KNOWN_GAPS: dict[tuple[str, str], str] = {
    # ── json_extract: path syntax ────────────────────────────────────────────
    (
        "OLC-T-010i",
        "polars",
    ): "Polars cannot COMPILE a quoted JSON path key ($.\"my key\") and aborts the run "
    "(ComputeError: 'error compiling JSON path expression path error: Eof'). Keys "
    "containing spaces are unreachable on this engine.",
    # ── json_extract: casts ──────────────────────────────────────────────────
    (
        "OLC-T-010k",
        "polars",
    ): "Polars returns NULL for cast: timestamp — the extracted JSON string is not "
    "parsed into a timestamp (str.to_datetime is never applied), so a declared "
    "timestamp column silently arrives empty. cast: decimal works.",
    # ── nested types: serialising a native container into a string field ─────
    (
        "OLC-N-001",
        "duckdb",
    ): "DuckDB renders a native struct into a string field as a DuckDB struct literal "
    "(\"{'a': 1, 'b': x}\") — not JSON: keys are single-quoted and the string member "
    "is unquoted, so the result cannot be parsed back by any JSON reader.",
    (
        "OLC-N-001",
        "polars",
    ): "Polars renders a native struct into a string field POSITIONALLY ('{1,\"x\"}'), "
    "DISCARDING the field names. This is lossy: the struct's keys cannot be "
    "recovered from the stored value.",
    (
        "OLC-N-002",
        "duckdb",
    ): "DuckDB renders a native array into a string field as '[a, b, c]' — the string "
    "elements are unquoted, so the value is not valid JSON and does not round-trip.",
    # ── nested types: drift INSIDE a struct ──────────────────────────────────
    (
        "OLC-N-004",
        "duckdb",
    ): "Struct-internal drift is UNDETECTED: the declared member 'b' is absent from "
    "the incoming struct and the row is accepted. LakeLogic's drift check compares "
    "top-level column names only, so a struct that lost half its members still "
    "satisfies a struct<a:int,b:string> declaration.",
    (
        "OLC-N-004",
        "polars",
    ): "Struct-internal drift is UNDETECTED: the declared member 'b' is absent from "
    "the incoming struct and the row is accepted. LakeLogic's drift check compares "
    "top-level column names only, so a struct that lost half its members still "
    "satisfies a struct<a:int,b:string> declaration.",
    # NOTE: Spark is deliberately NOT listed for OLC-N-004. It is the only engine
    # that detects the drift at all — it refuses the run rather than quarantining
    # the row, which the case accepts via `refusal_conforms`. Listing it here would
    # rank the one correct behaviour as the deviant one.
    # ── Spark: json_extract ──────────────────────────────────────────────────
    (
        "OLC-T-010e",
        "spark",
    ): "Spark also silently DROPS a phase:pre json_extract: the pre-phase quality "
    "rule sees a NULL 'lat' and quarantines BOTH rows instead of one. engines/spark.py "
    "never applies json_extract in the pre pass, and nothing reports the unhonoured "
    "phase.",
    (
        "OLC-T-010g",
        "spark",
    ): "Spark ABORTS the run on a value that does not fit the declared cast "
    "(CAST_INVALID_INPUT: \"The value 'abc' ... cannot be cast to 'DOUBLE'\"). "
    "engines/spark.py:694 uses the ANSI .cast() rather than try_cast.",
    (
        "OLC-T-010i",
        "spark",
    ): "Spark returns NULL for a quoted JSON path key ($.\"my key\") and reports no "
    "error — the WORST failure mode of the three engines: get_json_object does not "
    "accept quoted keys, so the column is SILENTLY empty and a pipeline reading it "
    "cannot tell an absent key from an unsupported path syntax.",
    (
        "OLC-T-010k",
        "spark",
    ): "Spark leaves cast: decimal UNAPPLIED — 'amt' arrives as the STRING '12.34' "
    "rather than a number. The cast map at engines/spark.py:684-693 has no decimal "
    "entry (nor date/timestamp/datetime), and an unmapped cast is skipped silently "
    "instead of being refused.",
    # ── Spark: read-path JSON flattening ─────────────────────────────────────
    (
        "OLC-S-001",
        "spark",
    ): "Spark does NOT honour source.flatten_nested: the declared payload_a/payload_b "
    "arrive as NULL on every row and the rows are ACCEPTED anyway — silent data loss, "
    "the worst of the failure modes. processor._flatten_json_df (~:3129) converts the "
    "frame via df.to_dict(orient='records') inside a bare `except Exception: return "
    "df`; a Spark DataFrame has no .to_dict, so the flattening is skipped without a "
    "warning and the contract's declared columns are filled with nulls. Works on "
    "DuckDB and Polars.",
    # ── Spark: nested type serialisation ─────────────────────────────────────
    (
        "OLC-N-001",
        "spark",
    ): "Spark renders a native struct into a string field POSITIONALLY ('{1, x}') — "
    "field names are DISCARDED and the string member is unquoted, so the value is "
    "neither valid JSON nor round-trippable.",
    (
        "OLC-N-002",
        "spark",
    ): "Spark renders a native array into a string field as '[a, b, c]' — elements "
    "unquoted, so the value is not valid JSON and does not round-trip.",
}


def _needs_delta(case) -> bool:
    return case.is_materialization and (case.materialization.format == "delta")


@pytest.mark.parametrize("adapter_name", ADAPTER_NAMES)
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_case_conforms(case, adapter_name, request):
    if _needs_delta(case):
        _require("deltalake", "deltalake not installed")
    gap = KNOWN_GAPS.get((case.id, adapter_name))
    if gap:
        request.applymarker(pytest.mark.xfail(strict=True, reason=gap))

    outcome = run_case(case, adapter_name)

    if case.level in REQUIRED_LEVELS:
        # Core features must actually work — UNSUPPORTED is not success here.
        assert outcome.status == PASS, (
            f"{case.id} ({case.level}) on {adapter_name}: {outcome.status} "
            f"(required level must PASS)\n" + "\n".join(outcome.reasons)
        )
    else:
        assert outcome.status in (PASS, UNSUPPORTED), (
            f"{case.id} on {adapter_name}: {outcome.status}\n"
            + "\n".join(outcome.reasons)
        )


def test_all_case_contracts_are_strict_valid():
    """Every case contract must pass strict OLCContractV1 validation.

    Guards against future cases sneaking in through the lenient runtime path: a
    conformance contract that isn't itself a valid canonical OLC contract is not a
    legitimate case. Uses the PUBLIC model, so this holds independent of the runtime.

    Exception: cases asserting ``expects_error`` carry a DELIBERATELY invalid
    contract — proving that an invalid contract is refused requires an invalid
    contract. Those are inverted below: they must FAIL strict validation, so the
    exemption can't be used to smuggle in a broken case that merely happens to be
    broken.
    """
    from olc.models import load_strict

    failures = []
    for case in CASES:
        must_be_refused = bool(case.assertions.get("expects_error"))
        try:
            load_strict(case.contract)
            if must_be_refused:
                failures.append(
                    f"{case.id}: declares expects_error but its contract is VALID — "
                    f"the case cannot prove a refusal"
                )
        except Exception as exc:  # noqa: BLE001 - report, don't abort
            if not must_be_refused:
                failures.append(f"{case.id}: {type(exc).__name__}: {str(exc)[:160]}")
    assert not failures, "case contracts fail strict validation:\n" + "\n".join(
        failures
    )


def test_public_model_matches_runtime_model():
    """The public OLCContractV1 and the LakeLogic runtime's copy must not diverge.

    Until the runtime formally consumes the public package (dependency inversion),
    both definitions exist; this guard fails the moment their emitted shapes drift,
    so the "LakeLogic implements the same standard" claim stays true. Descriptions
    (docstrings) are allowed to differ; structure is not.
    """
    try:
        from lakelogic.core.contracts import OLCContractV1 as RuntimeModel
    except Exception:
        if REQUIRE:
            raise
        pytest.skip("LakeLogic runtime strict model unavailable")
    from olc.models import OLCContractV1 as PublicModel

    def _strip(o):
        if isinstance(o, dict):
            return {k: _strip(v) for k, v in o.items() if k != "description"}
        if isinstance(o, list):
            return [_strip(x) for x in o]
        return o

    assert _strip(PublicModel.model_json_schema()) == _strip(
        RuntimeModel.model_json_schema()
    ), (
        "Public olc.models.OLCContractV1 has drifted from the LakeLogic runtime model. "
        "Re-sync them (ultimately: make the runtime import the public model)."
    )


def test_corpus_is_nonempty():
    assert CASES, "no conformance cases discovered"


def test_case_ids_are_unique():
    """Two cases sharing an id makes the corpus unciteable.

    Case ids are the citation handle used by the spec, the schema descriptions and
    the docs ("conformance case OLC-T-002"). When two directories claim the same id
    a reader cannot tell which behaviour is actually pinned, and KNOWN_GAPS keys —
    which are (case_id, adapter) — silently apply to both. ``filter-post`` and
    ``dedup-unordered-refused`` both claimed OLC-T-002 until this guard was added.
    """
    seen: dict[str, list[str]] = {}
    for case in CASES:
        seen.setdefault(case.id, []).append(case.directory.name)
    dupes = {cid: dirs for cid, dirs in seen.items() if len(dirs) > 1}
    assert not dupes, "duplicate conformance case ids: " + "; ".join(
        f"{cid} -> {sorted(dirs)}" for cid, dirs in sorted(dupes.items())
    )


def test_cross_engine_agreement():
    """DuckDB and Polars must reach the same status on every case (bar known gaps)."""
    disagreements = []
    for case in CASES:
        if any((case.id, name) in KNOWN_GAPS for name in ADAPTER_NAMES):
            continue  # tracked separately as a strict xfail
        statuses = {name: run_case(case, name).status for name in ADAPTER_NAMES}
        if len(set(statuses.values())) > 1:
            disagreements.append(f"{case.id}: {statuses}")
    assert not disagreements, "cross-engine disagreement:\n" + "\n".join(disagreements)


def test_capability_matrix(capsys):
    """Report (never assert) which optional features each adapter does not support.

    Required-level coverage is enforced by ``test_case_conforms``; this surfaces
    UNSUPPORTED results separately so they are visible, not silently green.
    """
    rows = []
    for case in CASES:
        for name in ADAPTER_NAMES:
            status = run_case(case, name).status
            if status == UNSUPPORTED:
                rows.append(f"  {case.id:16} {case.feature:24} {name}: UNSUPPORTED")
    with capsys.disabled():
        if rows:
            print("\nCapability matrix (unsupported optional features):")
            print("\n".join(rows))
        else:
            print(
                "\nCapability matrix: all declared features supported by all adapters."
            )
