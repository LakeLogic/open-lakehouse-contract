"""docs/llms.txt and llms-full.txt: current, every link real, every example a contract worth copying.

llms.txt is what an LLM reads to write an OLC contract. A stale file, a dead link or an example
that fails validation or lint would teach it the wrong thing.
"""

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from olc.models import load_strict
from olc.validate import load_contract_yaml

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://olc.lakelogic.io"
EXAMPLES = sorted((ROOT / "examples").glob("*.olc.yaml"))


class LlmsTxt(unittest.TestCase):
    def test_the_files_are_current(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "generate_llms.py"), "--check"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_every_link_into_the_docs_site_exists(self):
        text = (ROOT / "docs" / "llms.txt").read_text(encoding="utf-8")
        links = re.findall(r"\((" + re.escape(SITE) + r"[^)]+)\)", text)
        self.assertGreater(len(links), 10)
        for url in links:
            rel = url[len(SITE) :].lstrip("/")
            local = ROOT / "docs" / (rel[:-5] + ".md" if rel.endswith(".html") else rel)
            self.assertTrue(
                local.exists(),
                f"llms.txt links to {url}, but docs/{local.relative_to(ROOT / 'docs')} does not exist",
            )


class Skeleton(unittest.TestCase):
    """The key-placement skeleton in llms.txt is copied verbatim by LLMs: it must be a clean contract."""

    def test_the_skeleton_is_valid_and_lint_clean(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import generate_llms

        doc = load_contract_yaml(generate_llms.SKELETON)
        load_strict(doc)
        try:
            from lakelogic.core.contract_lint import review_contract_dict
        except Exception:  # pragma: no cover
            self.skipTest("LakeLogic not installed; the release gate runs this with it")
        self.assertEqual(
            [f.check_id for f in review_contract_dict(doc, "skeleton")], []
        )


class Examples(unittest.TestCase):
    """The examples are what llms.txt shows and what people copy."""

    def test_there_are_examples(self):
        self.assertGreaterEqual(len(EXAMPLES), 2)

    def test_every_example_is_a_strictly_valid_contract(self):
        for path in EXAMPLES:
            with self.subTest(example=path.name):
                load_strict(load_contract_yaml(path.read_text(encoding="utf-8")))

    def test_every_example_passes_the_json_schema(self):
        schema = json.loads(
            (ROOT / "schema" / "open-lakehouse-contract.schema.json").read_text(
                encoding="utf-8"
            )
        )
        validator = Draft202012Validator(schema)
        for path in EXAMPLES:
            with self.subTest(example=path.name):
                doc = load_contract_yaml(path.read_text(encoding="utf-8"))
                errors = [e.message for e in validator.iter_errors(doc)]
                self.assertEqual(errors, [])

    def test_every_example_passes_lakelogic_lint(self):
        try:
            from lakelogic.core.contract_lint import review_contract
        except (
            Exception
        ):  # pragma: no cover - the reference runtime is optional for the standard
            self.skipTest("LakeLogic not installed; the release gate runs this with it")
        for path in EXAMPLES:
            with self.subTest(example=path.name):
                self.assertEqual([f.check_id for f in review_contract(path)], [])


if __name__ == "__main__":
    unittest.main()
