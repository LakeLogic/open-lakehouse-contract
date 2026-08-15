from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from olc import init


class InitCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.skills = self.root / "skills"
        self.source = self.skills / "testtool"
        self.source.mkdir(parents=True)
        (self.source / "instructions.md").write_text(
            "OLC INSTRUCTIONS\n", encoding="utf-8"
        )
        (self.source / "second.md").write_text("SECOND\n", encoding="utf-8")
        self.dest = self.root / "project"
        self.dest.mkdir()
        self.patches = (
            patch.object(init, "SKILLS", self.skills),
            patch.object(init, "INSTALLERS", {"testtool": [("testtool", ".agent")]}),
        )
        for active_patch in self.patches:
            active_patch.start()

    def tearDown(self) -> None:
        for active_patch in reversed(self.patches):
            active_patch.stop()
        self.temp.cleanup()

    def run_init(self, *args: str) -> tuple[int, str]:
        output = io.StringIO()
        with redirect_stdout(output):
            code = init.main(list(args))
        return code, output.getvalue()

    def test_creates_new_files(self) -> None:
        code, output = self.run_init("--tools", "testtool", "--dest", str(self.dest))
        self.assertEqual(code, 0)
        self.assertEqual(
            (self.dest / ".agent" / "instructions.md").read_text(encoding="utf-8"),
            "OLC INSTRUCTIONS\n",
        )
        self.assertIn("2 create", output)

    def test_identical_files_are_left_unchanged(self) -> None:
        self.run_init("--tools", "testtool", "--dest", str(self.dest))
        code, output = self.run_init("--tools", "testtool", "--dest", str(self.dest))
        self.assertEqual(code, 0)
        self.assertIn("2 unchanged", output)

    def test_conflict_aborts_before_any_write(self) -> None:
        target = self.dest / ".agent" / "instructions.md"
        target.parent.mkdir(parents=True)
        target.write_text("USER CONTENT\n", encoding="utf-8")
        code, output = self.run_init("--tools", "testtool", "--dest", str(self.dest))
        self.assertEqual(code, 1)
        self.assertEqual(target.read_text(encoding="utf-8"), "USER CONTENT\n")
        self.assertFalse((self.dest / ".agent" / "second.md").exists())
        self.assertIn("nothing was changed", output)

    def test_force_overwrites_conflict(self) -> None:
        target = self.dest / ".agent" / "instructions.md"
        target.parent.mkdir(parents=True)
        target.write_text("USER CONTENT\n", encoding="utf-8")
        code, output = self.run_init(
            "--tools", "testtool", "--dest", str(self.dest), "--force"
        )
        self.assertEqual(code, 0)
        self.assertEqual(target.read_text(encoding="utf-8"), "OLC INSTRUCTIONS\n")
        self.assertIn("1 overwrite", output)

    def test_dry_run_writes_nothing(self) -> None:
        code, output = self.run_init(
            "--tools", "testtool", "--dest", str(self.dest), "--dry-run"
        )
        self.assertEqual(code, 0)
        self.assertFalse((self.dest / ".agent").exists())
        self.assertIn("DRY RUN", output)

    def test_dry_run_reports_conflicts_without_overwriting(self) -> None:
        target = self.dest / ".agent" / "instructions.md"
        target.parent.mkdir(parents=True)
        target.write_text("USER CONTENT\n", encoding="utf-8")
        code, output = self.run_init(
            "--tools", "testtool", "--dest", str(self.dest), "--dry-run"
        )
        self.assertEqual(code, 1)
        self.assertEqual(target.read_text(encoding="utf-8"), "USER CONTENT\n")
        self.assertIn("CONFLICT", output)

    def test_unknown_tool_is_usage_error(self) -> None:
        code, output = self.run_init("--tools", "unknown", "--dest", str(self.dest))
        self.assertEqual(code, 2)
        self.assertIn("unknown integration", output)

    def test_directory_collision_is_never_overwritten(self) -> None:
        target = self.dest / ".agent" / "instructions.md"
        target.mkdir(parents=True)
        code, output = self.run_init(
            "--tools", "testtool", "--dest", str(self.dest), "--force"
        )
        self.assertEqual(code, 1)
        self.assertTrue(target.is_dir())
        self.assertIn("unsafe destinations", output)


if __name__ == "__main__":
    unittest.main()
