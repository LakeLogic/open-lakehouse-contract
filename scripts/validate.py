"""Validate Open Lakehouse Contract files against the published JSON Schema.

No runtime required — just a JSON-Schema validator. Point it at your `*.olc.yaml`
files (or let it discover them) to check them in CI, right beside your SQL / dbt /
PySpark. This is the "OLC sits next to my code" entry point: it needs only
`jsonschema` + `pyyaml`, never LakeLogic.

    pip install jsonschema pyyaml
    python scripts/validate.py                         # discover **/*.olc.yaml
    python scripts/validate.py path/to/contract.olc.yaml ...
    python scripts/validate.py --schema https://…/open-lakehouse-contract.schema.json  contracts/*.olc.yaml

Exit code is non-zero if any file fails, so it works as a CI gate.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
import urllib.request
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = ROOT / "schema" / "open-lakehouse-contract.schema.json"


def _load_schema(ref: str) -> dict:
    if ref.startswith(("http://", "https://")):
        with urllib.request.urlopen(ref) as r:  # noqa: S310 - user-supplied schema URL
            return json.loads(r.read().decode("utf-8"))
    return json.loads(Path(ref).read_text(encoding="utf-8"))


def _discover() -> list[Path]:
    out: list[Path] = []
    for pat in ("**/*.olc.yaml", "**/*.olc.yml"):
        out += [Path(p) for p in glob.glob(pat, recursive=True)]
    return sorted(set(out))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Validate OLC contract files against the JSON Schema.")
    ap.add_argument("files", nargs="*", help="Contract files (default: discover **/*.olc.yaml)")
    ap.add_argument("--schema", default=str(DEFAULT_SCHEMA), help="Schema path or https URL")
    args = ap.parse_args(argv)

    validator = Draft202012Validator(_load_schema(args.schema))
    files = [Path(f) for f in args.files] or _discover()
    if not files:
        print("No .olc.yaml files found — nothing to validate.")
        return 0

    failed = 0
    for f in files:
        try:
            doc = yaml.safe_load(f.read_text(encoding="utf-8"))
            errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
        except Exception as e:  # unreadable / not YAML
            failed += 1
            print(f"FAIL  {f}\n      -> {e}")
            continue
        if errors:
            failed += 1
            print(f"FAIL  {f}")
            for e in errors[:10]:
                loc = ".".join(str(p) for p in e.path) or "<root>"
                print(f"      -> {loc}: {e.message}")
        else:
            print(f"OK    {f}")

    print(f"\n{'FAIL' if failed else 'OK'} - {len(files)} file(s), {failed} invalid")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
