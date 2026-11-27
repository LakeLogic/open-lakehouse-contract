"""The ``olc`` command — a thin dispatcher over the subcommands.

olc validate [files...] [--schema PATH|URL]
olc init [--tools claude,codex] [--dest .] [--list]
olc guide | olc reference [Section]
"""

from __future__ import annotations

import sys
from importlib.metadata import PackageNotFoundError, version

USAGE = """olc — Open Lakehouse Contract CLI

Usage:
  olc validate [files...] [--schema PATH|URL]   Validate *.olc.yaml against the JSON Schema
  olc init [--tools claude,codex] [--dest .]    Install agent integrations safely
  olc guide                                      Agent guide: tasks, every key, common shapes
  olc reference [Section]                        Field reference: every key, type and default
  olc --version                                  Print the installed CLI version

Run `olc <command> --help` for command options.
"""


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0 if argv else 2

    if argv[0] in ("-V", "--version"):
        try:
            release = version("open-lakehouse-contract")
        except PackageNotFoundError:
            release = "development"
        print(f"olc {release}")
        return 0

    cmd, rest = argv[0], argv[1:]
    if cmd == "validate":
        from . import validate

        return validate.main(rest)
    if cmd == "init":
        from . import init

        return init.main(rest)

    if cmd in ("guide", "reference"):
        return _print_skill(cmd, rest)

    print(f"Unknown command: {cmd}\n")
    print(USAGE)
    return 2


def _print_skill(cmd: str, rest: list[str]) -> int:
    """Print the agent guide or the field reference, from the files this release ships, so any
    agent with a shell can read the format without a repo checkout (2026-11-18)."""
    from .init import SKILLS

    if cmd == "guide":
        text = (SKILLS / "agents" / "AGENTS.md").read_text(encoding="utf-8")
        start = text.find("# Open Lakehouse Contract — agent guide")
        print(text[start:] if start >= 0 else text)
        return 0
    text = (SKILLS / "olc-reference.md").read_text(encoding="utf-8")
    if not rest:
        print(text)
        return 0
    want = " ".join(rest).strip().lower()  # "Top level" arrives as two arguments
    sections = text.split("\n## ")
    title = lambda s: s.split("\n", 1)[0].strip()  # noqa: E731
    for s in sections[1:]:
        if title(s).lower() == want:
            print("## " + s.rstrip())
            return 0
    names = ", ".join(title(s) for s in sections[1:])
    print(f"No section '{rest[0]}'. Sections: {names}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
