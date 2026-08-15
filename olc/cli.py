"""The ``olc`` command — a thin dispatcher over the subcommands.

olc validate [files...] [--schema PATH|URL]
olc init [--tools claude,codex] [--dest .] [--list]
"""

from __future__ import annotations

import sys
from importlib.metadata import PackageNotFoundError, version

USAGE = """olc — Open Lakehouse Contract CLI

Usage:
  olc validate [files...] [--schema PATH|URL]   Validate *.olc.yaml against the JSON Schema
  olc init [--tools claude,codex] [--dest .]    Install agent integrations safely
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

    print(f"Unknown command: {cmd}\n")
    print(USAGE)
    return 2


if __name__ == "__main__":
    sys.exit(main())
