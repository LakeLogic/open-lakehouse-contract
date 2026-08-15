from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from olc import validate


VALID_CONTRACT = """\
version: 1.0.0
info:
  title: Test
  table_name: test
model:
  fields:
    - name: id
      type: integer
"""


class ValidateCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_validate(self, *args: str) -> tuple[int, str]:
        output = io.StringIO()
        with redirect_stdout(output):
            code = validate.main(list(args))
        return code, output.getvalue()

    def write(self, relative: str, content: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_valid_file_passes(self) -> None:
        path = self.write("valid.olc.yaml", VALID_CONTRACT)
        code, output = self.run_validate(str(path))
        self.assertEqual(code, 0)
        self.assertIn("OK", output)

    def test_invalid_file_returns_one(self) -> None:
        path = self.write("invalid.olc.yaml", VALID_CONTRACT + "qualitty: {}\n")
        code, output = self.run_validate(str(path))
        self.assertEqual(code, 1)
        self.assertIn("Additional properties", output)

    def test_duplicate_yaml_key_is_rejected(self) -> None:
        path = self.write("duplicate.olc.yaml", VALID_CONTRACT + "version: 2.0.0\n")
        code, output = self.run_validate(str(path))
        self.assertEqual(code, 1)
        self.assertIn("duplicate key 'version'", output)

    def test_json_output_is_machine_readable(self) -> None:
        path = self.write("valid.olc.yaml", VALID_CONTRACT)
        code, output = self.run_validate(str(path), "--output", "json")
        payload = json.loads(output)
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["files"], 1)
        self.assertTrue(payload["results"][0]["valid"])

    def test_discovery_is_recursive(self) -> None:
        self.write("nested/deeper/contract.olc.yml", VALID_CONTRACT)
        code, output = self.run_validate("--root", str(self.root))
        self.assertEqual(code, 0)
        self.assertIn("contract.olc.yml", output)

    def test_empty_discovery_fails_by_default(self) -> None:
        code, output = self.run_validate("--root", str(self.root))
        self.assertEqual(code, 1)
        self.assertIn("No .olc.yaml", output)

    def test_allow_empty_is_explicit(self) -> None:
        code, _ = self.run_validate("--root", str(self.root), "--allow-empty")
        self.assertEqual(code, 0)

    def test_schema_load_failure_has_clean_exit(self) -> None:
        code, output = self.run_validate("--schema", str(self.root / "missing.json"), "--allow-empty")
        self.assertEqual(code, 2)
        self.assertIn("ERROR schema", output)

    def test_plain_http_schema_is_rejected(self) -> None:
        code, output = self.run_validate("--schema", "http://example.com/schema.json", "--allow-empty")
        self.assertEqual(code, 2)
        self.assertIn("must use HTTPS", output)


if __name__ == "__main__":
    unittest.main()
