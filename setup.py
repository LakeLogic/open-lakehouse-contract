"""Build shim: vendor schema/ + skills/ into the olc package so the wheel is
self-contained (project metadata lives in pyproject.toml).

The repo keeps schema/ and skills/ at the root (referenced by CI, docs, scripts);
this copies them into olc/_bundled/ at build time so `olc validate` (schema) and
`olc init` (skill templates) work from a plain `pip install` — not just editable.
"""

import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py

ROOT = Path(__file__).parent


class build_py_with_bundle(build_py):
    def run(self):
        bundle = ROOT / "olc" / "_bundled"
        for name in ("schema", "skills"):
            src, dst = ROOT / name, bundle / name
            if src.exists():
                shutil.rmtree(dst, ignore_errors=True)
                shutil.copytree(src, dst)
        super().run()


setup(cmdclass={"build_py": build_py_with_bundle})
