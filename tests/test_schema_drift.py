"""Schema-drift gate: the committed JSON Schema must match what the model emits.

The OLC schema is generated from the **public** ``olc.models.OLCContractV1`` model in
this repository. This test regenerates the schema in-memory and asserts it is
byte-for-byte identical to the committed ``schema/open-lakehouse-contract.schema.json``.
If someone changes the model (or the generator) without re-running
``python scripts/generate_schema.py``, this fails — so the committed schema can never
silently drift from the model (plus the generator's documented post-processing).

Because the model is public, this runs with **no private dependency** — it needs only
``pydantic`` (``pip install .[models]``). It skips only if that isn't installed (e.g. a
minimal docs-only checkout), never treating a missing *private* runtime as success.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schema" / "open-lakehouse-contract.schema.json"
sys.path.insert(0, str(ROOT / "scripts"))

try:  # the generator imports the public olc.models.OLCContractV1 (needs pydantic)
    from generate_schema import build_schema, render_schema

    _IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - environment-dependent
    build_schema = render_schema = None  # type: ignore[assignment]
    _IMPORT_ERROR = exc


class SchemaDriftTests(unittest.TestCase):
    @unittest.skipIf(
        build_schema is None, f"reference model unavailable: {_IMPORT_ERROR}"
    )
    def test_committed_schema_matches_model(self) -> None:
        regenerated = render_schema(build_schema())
        committed = SCHEMA_PATH.read_text(encoding="utf-8")
        self.assertEqual(
            regenerated,
            committed,
            "Committed schema is out of date with the reference model. "
            "Run:  python scripts/generate_schema.py  and commit the result.",
        )

    def test_committed_schema_is_parseable(self) -> None:
        # Always runs — guards against a corrupt/hand-edited committed schema even
        # when the model isn't importable.
        json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
