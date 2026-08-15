"""Validate Open Lakehouse Contract files against the published JSON Schema.

Structural validation only — depends on ``jsonschema`` + ``pyyaml``, never a runtime.
Importable (``from olc.validate import main``) and runnable (``olc validate``).
"""
from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path
from typing import Any, Union

import yaml
from jsonschema import Draft202012Validator

MAX_SCHEMA_BYTES = 10 * 1024 * 1024
SCHEMA_TIMEOUT_SECONDS = 10

def _default_schema() -> Path:
    """Locate the schema whether installed as a wheel (bundled under olc/_bundled/)
    or run from a source checkout (schema/ at the repo root)."""
    here = Path(__file__).resolve()
    for cand in (
        here.parent / "_bundled" / "schema" / "open-lakehouse-contract.schema.json",  # wheel
        here.parents[1] / "schema" / "open-lakehouse-contract.schema.json",           # editable / checkout
    ):
        if cand.is_file():
            return cand
    return here.parents[1] / "schema" / "open-lakehouse-contract.schema.json"


DEFAULT_SCHEMA = _default_schema()


def load_schema(ref: str) -> dict:
    if ref.startswith("http://"):
        raise ValueError("remote schemas must use HTTPS")
    if ref.startswith("https://"):
        request = urllib.request.Request(ref, headers={"User-Agent": "olc-validator"})
        with urllib.request.urlopen(request, timeout=SCHEMA_TIMEOUT_SECONDS) as response:
            raw = response.read(MAX_SCHEMA_BYTES + 1)
        if len(raw) > MAX_SCHEMA_BYTES:
            raise ValueError(f"remote schema exceeds {MAX_SCHEMA_BYTES} bytes")
        schema = json.loads(raw.decode("utf-8"))
    else:
        schema = json.loads(Path(ref).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


def discover(root: Union[str, Path] = ".") -> list[Path]:
    base = Path(root)
    return sorted({*base.rglob("*.olc.yaml"), *base.rglob("*.olc.yml")})


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(loader: UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def errors_for(doc: Any, validator: Draft202012Validator) -> list[str]:
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    out = []
    for e in errs:
        loc = ".".join(str(p) for p in e.path) or "<root>"
        out.append(f"{loc}: {e.message}")
    return out


def validate_file(path: Path, validator: Draft202012Validator) -> dict[str, Any]:
    try:
        doc = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
        errors = errors_for(doc, validator)
    except Exception as error:
        errors = [str(error)]
    return {"path": str(path), "valid": not errors, "errors": errors}


def _emit_text(results: list[dict[str, Any]], max_errors: int) -> None:
    for result in results:
        if result["valid"]:
            print(f"OK    {result['path']}")
            continue
        print(f"FAIL  {result['path']}")
        for error in result["errors"][:max_errors]:
            print(f"      -> {error}")
        hidden = len(result["errors"]) - max_errors
        if hidden > 0:
            print(f"      -> ... {hidden} more error(s)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="olc validate", description="Validate OLC contract files.")
    ap.add_argument("files", nargs="*", help="contract files; otherwise discover below --root")
    ap.add_argument("--root", default=".", help="discovery root when no files are supplied")
    ap.add_argument("--schema", default=str(DEFAULT_SCHEMA), help="schema path or HTTPS URL")
    ap.add_argument("--output", choices=("text", "json"), default="text", help="result format")
    ap.add_argument("--max-errors", type=int, default=10, help="errors shown per file in text output")
    ap.add_argument("--allow-empty", action="store_true", help="return success when discovery finds no files")
    args = ap.parse_args(argv)

    if args.max_errors < 1:
        ap.error("--max-errors must be at least 1")

    try:
        validator = Draft202012Validator(load_schema(args.schema))
    except Exception as error:
        payload = {"status": "error", "kind": "schema", "message": str(error)}
        print(json.dumps(payload, indent=2) if args.output == "json" else f"ERROR schema: {error}")
        return 2

    files = [Path(f) for f in args.files] if args.files else discover(args.root)
    if not files:
        payload = {
            "status": "ok" if args.allow_empty else "error",
            "files": 0,
            "invalid": 0,
            "results": [],
            "message": "No .olc.yaml or .olc.yml files found",
        }
        print(json.dumps(payload, indent=2) if args.output == "json" else payload["message"] + ".")
        return 0 if args.allow_empty else 1

    results = [validate_file(path, validator) for path in files]
    failed = sum(not result["valid"] for result in results)
    payload = {
        "status": "fail" if failed else "ok",
        "files": len(results),
        "invalid": failed,
        "results": results,
    }
    if args.output == "json":
        print(json.dumps(payload, indent=2))
    else:
        _emit_text(results, args.max_errors)
        print(f"\n{'FAIL' if failed else 'OK'} - {len(results)} file(s), {failed} invalid")
    return 1 if failed else 0
