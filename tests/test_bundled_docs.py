"""The bundled reference docs are what an agent reads from the installed package.

setup.py copies docs/reference/ and docs/providers/ into olc/_bundled/docs/ at build
time. These tests pin that the copy is complete and current, and that it resolves
through importlib.resources the way an installed reader will open it.
"""

import unittest
from importlib import resources
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLED = ROOT / "olc" / "_bundled" / "docs"


class BundledDocsTests(unittest.TestCase):
    def _assert_mirrors(self, folder: str) -> None:
        src = sorted(p.name for p in (ROOT / "docs" / folder).glob("*.md"))
        dst = sorted(p.name for p in (BUNDLED / folder).glob("*.md"))
        self.assertTrue(src, f"docs/{folder} has no pages")
        self.assertEqual(src, dst, f"bundled docs/{folder} is missing or has extra pages")
        for name in src:
            self.assertEqual(
                (ROOT / "docs" / folder / name).read_bytes(),
                (BUNDLED / folder / name).read_bytes(),
                f"bundled docs/{folder}/{name} is stale — rebuild or re-sync",
            )

    def test_reference_docs_are_bundled_and_current(self) -> None:
        self._assert_mirrors("reference")

    def test_provider_docs_are_bundled_and_current(self) -> None:
        self._assert_mirrors("providers")

    def test_bundled_docs_resolve_through_importlib_resources(self) -> None:
        page = resources.files("olc").joinpath("_bundled/docs/reference/ingestion.md")
        self.assertIn("type: dlt", page.read_text(encoding="utf-8"))
        providers = resources.files("olc").joinpath("_bundled/docs/providers/index.md")
        self.assertTrue(providers.is_file())


if __name__ == "__main__":
    unittest.main()
