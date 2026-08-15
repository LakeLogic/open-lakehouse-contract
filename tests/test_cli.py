from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

from olc import cli


class CliTests(unittest.TestCase):
    def capture(self, *args: str) -> tuple[int, str]:
        output = io.StringIO()
        with redirect_stdout(output):
            code = cli.main(list(args))
        return code, output.getvalue()

    def test_help(self) -> None:
        code, output = self.capture("--help")
        self.assertEqual(code, 0)
        self.assertIn("Open Lakehouse Contract CLI", output)

    def test_version(self) -> None:
        code, output = self.capture("--version")
        self.assertEqual(code, 0)
        self.assertRegex(output, r"^olc (?:development|\d+\.\d+\.\d+)")

    def test_unknown_command(self) -> None:
        code, output = self.capture("unknown")
        self.assertEqual(code, 2)
        self.assertIn("Unknown command", output)


if __name__ == "__main__":
    unittest.main()
