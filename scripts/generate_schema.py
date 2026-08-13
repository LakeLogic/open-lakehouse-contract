"""Regenerate the Open Lakehouse Contract JSON Schema from the reference implementation.

The OLC spec is not hand-maintained — it is *derived* from LakeLogic's Pydantic
`DataContract` model (the reference runtime), so the standard and the implementation
can never drift. Run this whenever the reference model changes.

    pip install lakelogic
    python scripts/generate_schema.py
"""
from __future__ import annotations

import json
from pathlib import Path

from lakelogic.core.models import DataContract  # the reference implementation

OUT = Path(__file__).resolve().parents[1] / "schema" / "open-lakehouse-contract.schema.json"
SCHEMA_URI = "https://json-schema.org/draft/2020-12/schema"
ID = "https://lakelogic.org/open-lakehouse-contract/v1/schema.json"


def main() -> None:
    schema = DataContract.model_json_schema()
    schema = {"$schema": SCHEMA_URI, "$id": ID, "title": "Open Lakehouse Contract", **schema}
    OUT.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(OUT.parents[1])}")
    print(f"  top-level fields : {len(schema.get('properties', {}))}")
    print(f"  nested models    : {len(schema.get('$defs', {}))}")


if __name__ == "__main__":
    main()
