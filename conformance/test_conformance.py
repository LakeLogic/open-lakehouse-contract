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
# (Empty: OLC-EO-001's Polars pre-phase ordering bug — the corpus's first find —
# was fixed in engines/polars.py by guarding the post-pass derive against re-running
# pre-phase transforms. Left here as the tracking mechanism for the next gap.)
KNOWN_GAPS: dict[tuple[str, str], str] = {}


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
    """
    from olc.models import load_strict

    failures = []
    for case in CASES:
        try:
            load_strict(case.contract)
        except Exception as exc:  # noqa: BLE001 - report, don't abort
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
