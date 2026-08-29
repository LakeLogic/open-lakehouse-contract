"""Load cases, run them through adapters, and compare against authored expectations.

Outcomes follow the capability-profile discipline: a feature an adapter does not
declare is UNSUPPORTED (never silently PASS); a declared feature that misbehaves
is FAIL.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .adapters import ADAPTERS, ConformanceAdapter
from .model import Comparison, ConformanceCase, ExecutionResult, Materialization
from .normalise import normalise_rows


class _NoBoolOnLoader(yaml.SafeLoader):
    """YAML loader that does NOT coerce on/off/yes/no to booleans.

    OLC contracts use keys like ``on:`` (lookup/deduplicate). Default YAML parses
    ``on`` as boolean ``True``, corrupting the key — the runtime avoids this, so the
    conformance harness must too.
    """


for _key, _mappings in list(_NoBoolOnLoader.yaml_implicit_resolvers.items()):
    _NoBoolOnLoader.yaml_implicit_resolvers[_key] = [
        (tag, regex) for tag, regex in _mappings if tag != "tag:yaml.org,2002:bool"
    ]
_NoBoolOnLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|false)$", re.IGNORECASE),
    list("tTfF"),
)


def _load_yaml(text: str) -> Any:
    return yaml.load(text, Loader=_NoBoolOnLoader)


CASES_DIR = Path(__file__).resolve().parents[1] / "cases"

PASS = "PASS"
FAIL = "FAIL"
UNSUPPORTED = "UNSUPPORTED"
SKIP = "SKIP"


@dataclass
class Outcome:
    case_id: str
    adapter: str
    status: str
    reasons: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True ONLY for a genuine pass. UNSUPPORTED/SKIP are not success.

        A caller using ``run_all()`` and checking ``ok`` gets a truthful signal;
        UNSUPPORTED results are surfaced separately via ``acceptable_for_capability_report``.
        """
        return self.status == PASS

    @property
    def acceptable_for_capability_report(self) -> bool:
        """Non-failing statuses — a PASS, or a legitimately unsupported/skipped case.

        Use this (not ``ok``) when building a capability matrix, where an
        adapter not implementing an *optional* feature is expected, not a failure.
        Core-level enforcement (UNSUPPORTED must fail) lives in the pytest layer.
        """
        return self.status in (PASS, UNSUPPORTED, SKIP)


# ── loading ──────────────────────────────────────────────────────────────────


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_case(directory: Path) -> ConformanceCase:
    manifest = _load_yaml((directory / "case.yaml").read_text(encoding="utf-8"))
    contract = _load_yaml((directory / "contract.olc.yaml").read_text(encoding="utf-8"))
    expected = manifest.get("expected") or {}
    comp = manifest.get("comparison") or {}
    mat = manifest.get("materialization")

    def _exp(name: str) -> list[dict] | None:
        rel = expected.get(name)
        return _read_jsonl(directory / rel) if rel else None

    return ConformanceCase(
        id=manifest["id"],
        spec_version=str(manifest.get("spec_version", "1.0.0")),
        level=manifest.get("level", "core-runtime"),
        feature=manifest.get("feature", ""),
        description=manifest.get("description", ""),
        directory=directory,
        contract=contract,
        input_rows=_read_jsonl(directory / (manifest.get("input") or "input.jsonl")),
        expected_accepted=_exp("accepted"),
        expected_quarantined=_exp("quarantined"),
        expected_target=_exp("target"),
        assertions=manifest.get("assertions") or {},
        input_via=manifest.get("input_via", "frame"),
        comparison=Comparison(
            sort_by=comp.get("sort_by", []),
            numeric_tolerance=float(comp.get("numeric_tolerance", 1e-6)),
            ignore_fields=comp.get("ignore_fields", []),
        ),
        materialization=(
            Materialization(
                format=mat.get("format", "delta"),
                seed=mat.get("seed"),
                idempotent=bool(mat.get("idempotent", False)),
            )
            if mat
            else None
        ),
    )


def load_all_cases(cases_dir: Path = CASES_DIR) -> list[ConformanceCase]:
    dirs = sorted(
        p for p in cases_dir.iterdir() if p.is_dir() and (p / "case.yaml").exists()
    )
    return [load_case(d) for d in dirs]


# ── comparison ───────────────────────────────────────────────────────────────


def _norm(rows: list[dict], comp: Comparison) -> list[dict]:
    return normalise_rows(
        rows,
        sort_by=comp.sort_by,
        ignore_fields=set(comp.ignore_fields),
        numeric_tolerance=comp.numeric_tolerance,
    )


def compare_result(
    case: ConformanceCase, result: ExecutionResult, adapter: ConformanceAdapter
) -> Outcome:
    caps = getattr(adapter, "capabilities", set())
    if case.feature and caps and case.feature not in caps:
        return Outcome(
            case.id,
            adapter.name,
            UNSUPPORTED,
            [f"feature '{case.feature}' not declared"],
        )

    reasons: list[str] = []
    comp = case.comparison

    # Some cases pin THAT a breach must be enforced without mandating HOW. A struct
    # that lost a declared member is the motivating example: quarantining the row and
    # refusing the run are both honest enforcements of the same contract, and the
    # spec does not choose between them — only silent acceptance is wrong.
    #
    # Without this, the case had to pin one mechanism, which listed the engine that
    # refuses the run as non-conforming while the engines that accept the bad row
    # silently were merely "gaps" — ranking the safest behaviour as the deviant one.
    # This is deliberately narrow: it is opt-in per case, and it still cannot turn a
    # row that was ACCEPTED into a pass.
    if case.assertions.get("refusal_conforms") and result.exception is not None:
        return Outcome(
            case.id,
            adapter.name,
            PASS,
            [
                f"run refused ({result.exception.code}) — a conforming enforcement "
                "for this case; see the case README"
            ],
        )

    # An exception is only acceptable if the case explicitly expects one.
    expects_error = case.assertions.get("expects_error")
    if result.exception is not None and not expects_error:
        return Outcome(
            case.id,
            adapter.name,
            FAIL,
            [f"unexpected error: {result.exception.code}"],
        )

    # ...and a case that expects one MUST get one. Without this, `expects_error`
    # only *tolerated* an error, so a refusal case would report PASS against an
    # adapter that happily ran the contract it was supposed to reject — the exact
    # false-green a conformance suite exists to prevent.
    if expects_error and result.exception is None:
        return Outcome(
            case.id,
            adapter.name,
            FAIL,
            ["expected the contract to be REFUSED, but it ran successfully"],
        )

    # accepted rows
    if case.expected_accepted is not None:
        got = _norm(result.accepted, comp)
        want = _norm(case.expected_accepted, comp)
        if got != want:
            reasons.append(f"accepted mismatch: got {got} want {want}")

    # quarantined source rows
    if case.expected_quarantined is not None:
        got = _norm(result.quarantined, comp)
        want = _norm(case.expected_quarantined, comp)
        if got != want:
            reasons.append(f"quarantined mismatch: got {got} want {want}")

    # materialised target state
    if case.expected_target is not None:
        got = _norm(result.target_rows, comp)
        want = _norm(case.expected_target, comp)
        if got != want:
            reasons.append(f"target mismatch: got {got} want {want}")

    # idempotency
    if case.materialization and case.materialization.idempotent:
        second = result.run_metadata.get("idempotent_target_rows", [])
        if _norm(second, comp) != _norm(result.target_rows, comp):
            reasons.append("idempotency violated: target changed on identical re-run")

    # scalar + attribution assertions
    reasons.extend(_check_assertions(case, result))

    status = FAIL if reasons else PASS
    return Outcome(case.id, adapter.name, status, reasons)


def _check_assertions(case: ConformanceCase, result: ExecutionResult) -> list[str]:
    reasons: list[str] = []
    a = case.assertions
    meta = result.run_metadata

    def _eq(key: str, actual: Any):
        if key in a and a[key] != actual:
            reasons.append(f"{key}: expected {a[key]}, got {actual}")

    _eq("rows_input", meta.get("rows_input"))
    _eq("rows_accepted", meta.get("rows_accepted", len(result.accepted)))
    _eq("rows_quarantined", meta.get("rows_quarantined", len(result.quarantined)))

    if "failed_rules" in a:
        got = meta.get("failed_rules", {})
        for rule, count in a["failed_rules"].items():
            if got.get(rule) != count:
                reasons.append(
                    f"failed_rules[{rule}]: expected {count}, got {got.get(rule)}"
                )

    if "dataset_rules_failed" in a:
        got = set(meta.get("dataset_rules_failed", []))
        for rule in a["dataset_rules_failed"]:
            if rule not in got:
                reasons.append(
                    f"dataset_rules_failed: expected '{rule}' among {sorted(got)}"
                )
    return reasons


# ── orchestration ────────────────────────────────────────────────────────────


def run_case(case: ConformanceCase, adapter_name: str) -> Outcome:
    adapter = ADAPTERS[adapter_name]()
    result = adapter.execute(case)
    return compare_result(case, result, adapter)


def run_all(
    adapter_names: list[str] | None = None, cases_dir: Path = CASES_DIR
) -> list[Outcome]:
    names = adapter_names or list(ADAPTERS)
    cases = load_all_cases(cases_dir)
    return [run_case(c, n) for c in cases for n in names]
