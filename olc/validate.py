"""Validate Open Lakehouse Contract files against the published JSON Schema.

Structural validation only — depends on ``jsonschema`` + ``pyyaml``, never a runtime.
Importable (``from olc.validate import main``) and runnable (``olc validate``).
"""
from __future__ import annotations

import argparse
import glob
import json
import urllib.request
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

PKG_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = PKG_ROOT / "schema" / "open-lakehouse-contract.schema.json"


def load_schema(ref: str) -> dict:
    if str(ref).startswith(("http://", "https://")):
        with urllib.request.urlopen(str(ref)) as r:  # noqa: S310 - user-supplied schema URL
            return json.loads(r.read().decode("utf-8"))
    return json.loads(Path(ref).read_text(encoding="utf-8"))


def discover(root: str = ".") -> list[Path]:
    out: list[Path] = []
    for pat in ("**/*.olc.yaml", "**/*.olc.yml"):
        out += [Path(p) for p in glob.glob(str(Path(root) / pat), recursive=True)]
    return sorted(set(out))


def errors_for(doc: dict, validator: Draft202012Validator) -> list[str]:
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    out = []
    for e in errs:
        loc = ".".join(str(p) for p in e.path) or "<root>"
        out.append(f"{loc}: {e.message}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="olc validate", description="Validate OLC contract files.")
    ap.add_argument("files", nargs="*", help="Contract files (default: discover **/*.olc.yaml)")
    ap.add_argument("--schema", default=str(DEFAULT_SCHEMA), help="Schema path or https URL")
    args = ap.parse_args(argv)

    validator = Draft202012Validator(load_schema(args.schema))
    files = [Path(f) for f in args.files] or discover()
    if not files:
        print("No .olc.yaml files found — nothing to validate.")
        return 0

    failed = 0
    for f in files:
        try:
            doc = yaml.safe_load(f.read_text(encoding="utf-8"))
            errs = errors_for(doc, validator)
        except Exception as e:  # unreadable / not YAML
            failed += 1
            print(f"FAIL  {f}\n      -> {e}")
            continue
        if errs:
            failed += 1
            print(f"FAIL  {f}")
            for e in errs[:10]:
                print(f"      -> {e}")
        else:
            print(f"OK    {f}")

    print(f"\n{'FAIL' if failed else 'OK'} - {len(files)} file(s), {failed} invalid")
    return 1 if failed else 0
