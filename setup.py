"""Build shim: vendor schema/ + skills/ + reference docs into the olc package so the wheel is
self-contained (project metadata lives in pyproject.toml).

The repo keeps schema/ and skills/ at the root (referenced by CI, docs, scripts);
this copies them into olc/_bundled/ at build time so `olc validate` (schema) and
`olc init` (skill templates) work from a plain `pip install` — not just editable.

docs/reference/ and docs/providers/ are bundled to olc/_bundled/docs/ so an agent can
read the spec's prose from the installed package (importlib.resources) — only those two
folders, not the site chrome.
"""

import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py

ROOT = Path(__file__).parent


# (source under the repo root, destination under olc/_bundled/)
BUNDLE = (
    ("schema", "schema"),
    ("skills", "skills"),
    ("docs/reference", "docs/reference"),
    ("docs/providers", "docs/providers"),
)


class build_py_with_bundle(build_py):
    def run(self):
        bundle = ROOT / "olc" / "_bundled"
        for name, target in BUNDLE:
            src, dst = ROOT / name, bundle / target
            if src.exists():
                shutil.rmtree(dst, ignore_errors=True)
                shutil.copytree(src, dst)
        super().run()


setup(cmdclass={"build_py": build_py_with_bundle})
