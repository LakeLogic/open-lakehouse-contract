"""Canonical data structures for the OLC executable-conformance harness.

These types are engine-neutral: an adapter runs a case on a specific runtime and
returns an :class:`ExecutionResult`, which the comparator checks against the
case's authored expectations. Nothing here imports an engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class ExecutionError:
    """Stable, engine-neutral error surface (never raw exception text)."""

    category: str  # e.g. "dataset_quality_failure", "schema_error"
    code: str  # stable code, e.g. "OLC_DATASET_RULE_FAILED"
    message: str = ""  # human-readable; NOT asserted on


@dataclass
class ExecutionResult:
    """What every adapter must produce, normalised later before comparison."""

    accepted: list[dict]
    quarantined: list[dict]
    run_metadata: dict = field(default_factory=dict)
    target_rows: list[dict] = field(default_factory=list)
    exception: Optional[ExecutionError] = None


@dataclass
class Comparison:
    """How to compare rows for a case (semantic outcome, not physical form)."""

    sort_by: list[str] = field(default_factory=list)
    numeric_tolerance: float = 1e-6
    ignore_fields: list[str] = field(default_factory=list)


@dataclass
class Materialization:
    """Optional level-3 (materialisation) settings for a case."""

    format: str = "delta"
    seed: Optional[str] = None  # jsonl of prior target state
    idempotent: bool = False  # run twice; assert target run2 == run1


@dataclass
class ConformanceCase:
    """A single language-neutral behavioural case, loaded from a case directory."""

    id: str
    spec_version: str
    level: str  # document | core-runtime | materialization | operational | provider
    feature: str
    description: str
    directory: Path
    contract: dict
    input_rows: list[dict]
    expected_accepted: Optional[list[dict]] = None
    expected_quarantined: Optional[list[dict]] = None
    expected_target: Optional[list[dict]] = None
    assertions: dict[str, Any] = field(default_factory=dict)
    comparison: Comparison = field(default_factory=Comparison)
    materialization: Optional[Materialization] = None
    # How the input reaches the runtime.
    #   "frame"  — hand DataProcessor.run() an in-memory frame (the default, and
    #              what every case did before source-read cases existed).
    #   "source" — write the input to a file, point contract.source.path at it and
    #              call DataProcessor.run_source(). Required for any behaviour that
    #              lives in the READ path (e.g. source.flatten_nested), which
    #              run() never executes and so could not previously be tested.
    input_via: str = "frame"

    @property
    def is_materialization(self) -> bool:
        return self.materialization is not None

    @property
    def reads_from_source(self) -> bool:
        return self.input_via == "source"
