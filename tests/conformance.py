"""Conformance suite for the Open Lakehouse Contract.

Validates fixtures against the published JSON Schema (the language-neutral spec):
  * everything in examples/ and tests/valid/ MUST pass
  * everything in tests/invalid/ MUST fail

    pip install jsonschema pyyaml
    python tests/conformance.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schema" / "open-lakehouse-contract.schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA)


def _load(p: Path) -> dict:
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def _is_valid(doc: dict) -> tuple[bool, str]:
    errors = sorted(VALIDATOR.iter_errors(doc), key=lambda e: e.path)
    if not errors:
        return True, ""
    e = errors[0]
    return False, f"{list(e.path)}: {e.message}"


def main() -> int:
    failures = 0

    should_pass = sorted((ROOT / "examples").glob("*.yaml")) + sorted((ROOT / "tests" / "valid").glob("*.yaml"))
    for f in should_pass:
        ok, msg = _is_valid(_load(f))
        print(f"  {'PASS' if ok else 'FAIL'}  (expect valid)   {f.relative_to(ROOT)}")
        if not ok:
            print(f"        -> {msg}")
            failures += 1

    for f in sorted((ROOT / "tests" / "invalid").glob("*.yaml")):
        ok, _ = _is_valid(_load(f))
        print(f"  {'PASS' if not ok else 'FAIL'}  (expect invalid) {f.relative_to(ROOT)}")
        if ok:
            print("        -> unexpectedly validated")
            failures += 1

    print("\n" + ("OK  - all conformance checks passed" if failures == 0 else f"FAIL - {failures} check(s) failed"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
