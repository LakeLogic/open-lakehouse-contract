"""Unit tests for Outcome status semantics — no runtime dependency.

Locks down the contract that ``ok`` means ONLY a genuine PASS, while
``acceptable_for_capability_report`` also tolerates UNSUPPORTED / SKIP. This is
the guard that keeps an unimplemented core feature from ever reading as success.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from runner.harness import FAIL, PASS, SKIP, UNSUPPORTED, Outcome


def _outcome(status: str) -> Outcome:
    return Outcome(case_id="c", adapter="duckdb", status=status)


def test_ok_is_true_only_for_pass():
    assert _outcome(PASS).ok is True
    assert _outcome(FAIL).ok is False
    assert _outcome(UNSUPPORTED).ok is False
    assert _outcome(SKIP).ok is False


def test_capability_report_tolerates_unsupported_and_skip_but_not_fail():
    assert _outcome(PASS).acceptable_for_capability_report is True
    assert _outcome(UNSUPPORTED).acceptable_for_capability_report is True
    assert _outcome(SKIP).acceptable_for_capability_report is True
    assert _outcome(FAIL).acceptable_for_capability_report is False


def test_ok_and_capability_report_disagree_exactly_on_unsupported_skip():
    # The whole point of two properties: UNSUPPORTED/SKIP are "not a failure" for
    # a capability matrix, but they are NOT "success".
    for status in (UNSUPPORTED, SKIP):
        o = _outcome(status)
        assert o.ok is False
        assert o.acceptable_for_capability_report is True
