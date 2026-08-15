"""Install OLC agent integrations without destroying existing project files."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def _skills_root() -> Path:
    """Locate the skill templates whether installed as a wheel (bundled under
    olc/_bundled/) or run from a source checkout (skills/ at the repo root)."""
    here = Path(__file__).resolve()
    for cand in (here.parent / "_bundled" / "skills", here.parents[1] / "skills"):
        if cand.is_dir():
            return cand
    return here.parents[1] / "skills"


SKILLS = _skills_root()

# tool -> [(source under skills/, destination under the project root)]
INSTALLERS: dict[str, list[tuple[str, str]]] = {
    "claude": [
        ("claude/commands", ".claude/commands"),  # slash commands
        ("claude/skills", ".claude/skills"),  # Agent Skill
    ],
    "codex": [
        ("codex/prompts", ".codex/prompts"),  # custom prompts
    ],
    "cursor": [
        ("cursor/rules", ".cursor/rules"),  # project rule (.mdc)
    ],
    "copilot": [
        ("copilot", ".github"),  # .github/copilot-instructions.md
    ],
    "gemini": [
        ("gemini/root", "."),  # GEMINI.md
        ("gemini/commands", ".gemini/commands"),  # TOML slash commands
    ],
    "windsurf": [
        ("windsurf/rules", ".windsurf/rules"),  # rule (.md)
    ],
    "cline": [
        ("cline", ".clinerules"),  # .clinerules/*.md
    ],
    "agents": [
        ("agents", "."),  # AGENTS.md (shared standard: OpenCode, Q, Jules, Zed, …)
    ],
    "amazonq": [
        ("amazonq/rules", ".amazonq/rules"),  # Amazon Q Developer rule
    ],
    "roo": [
        ("roo/rules", ".roo/rules"),  # Roo Code rule
    ],
    "kilocode": [
        ("kilocode/rules", ".kilocode/rules"),  # Kilo Code rule
    ],
}


def _selected_tools(raw: str) -> tuple[list[str], list[str]]:
    requested = list(
        dict.fromkeys(part.strip() for part in raw.split(",") if part.strip())
    )
    if "all" in requested:
        return list(INSTALLERS), []
    return requested, [tool for tool in requested if tool not in INSTALLERS]


def _plan_files(
    tools: list[str], dest: Path
) -> tuple[list[tuple[Path, Path]], list[Path]]:
    """Return a de-duplicated copy plan and any missing template roots."""
    planned: dict[Path, Path] = {}
    missing: list[Path] = []
    for tool in tools:
        for source_relative, destination_relative in INSTALLERS[tool]:
            source_root = SKILLS / source_relative
            if not source_root.is_dir():
                missing.append(source_root)
                continue
            destination_root = dest / destination_relative
            for source in sorted(
                path for path in source_root.rglob("*") if path.is_file()
            ):
                planned[destination_root / source.relative_to(source_root)] = source
    return [(source, target) for target, source in sorted(planned.items())], missing


def _has_symlink_component(target: Path, dest: Path) -> bool:
    current = target
    while current != dest:
        if current.is_symlink():
            return True
        if current.parent == current:
            return True
        current = current.parent
    return False


def _state(source: Path, target: Path, dest: Path) -> str:
    if _has_symlink_component(target, dest):
        return "unsafe"
    if not target.exists():
        return "create"
    if not target.is_file():
        return "unsafe"
    return "identical" if source.read_bytes() == target.read_bytes() else "conflict"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="olc init", description="Install OLC agent integrations safely."
    )
    ap.add_argument(
        "--tools",
        default="claude",
        help=f"comma-separated integrations ({','.join(INSTALLERS)}) or 'all'",
    )
    ap.add_argument(
        "--dest", default=".", help="project root to install into (default: .)"
    )
    ap.add_argument(
        "--list", action="store_true", help="list available integrations and exit"
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="show changes without writing files"
    )
    ap.add_argument("--force", action="store_true", help="overwrite conflicting files")
    args = ap.parse_args(argv)

    if args.list:
        print("Available OLC agent integrations:")
        for t in INSTALLERS:
            print(f"  - {t}")
        print("  (use --tools all to install every one)")
        return 0

    tools, unknown = _selected_tools(args.tools)
    if unknown:
        print(f"ERROR unknown integration(s): {', '.join(unknown)}")
        print(f"Available: {', '.join(INSTALLERS)}")
        return 2
    if not tools:
        print("ERROR no integrations selected")
        return 2

    dest = Path(args.dest).resolve()
    plan, missing = _plan_files(tools, dest)
    if missing:
        for path in missing:
            print(f"ERROR missing bundled templates: {path}")
        return 2

    states = [(source, target, _state(source, target, dest)) for source, target in plan]
    unsafe = [(source, target) for source, target, state in states if state == "unsafe"]
    if unsafe:
        print(
            "ERROR unsafe destinations (directory or symbolic-link path); nothing was changed:"
        )
        for _, target in unsafe:
            print(f"  ! {target}")
        return 1

    conflicts = [
        (source, target) for source, target, state in states if state == "conflict"
    ]
    if conflicts and not args.force and not args.dry_run:
        print("ERROR existing files differ; nothing was changed:")
        for _, target in conflicts:
            print(f"  ! {target}")
        print("Re-run with --force to overwrite, or move/merge the files yourself.")
        return 1

    created = overwritten = identical = conflict_count = 0
    for source, target, state in states:
        if state == "conflict" and not args.force:
            action = "conflict"
        else:
            action = "overwrite" if state == "conflict" else state
        print(f"{action.upper():9} {target}")
        if state == "identical":
            identical += 1
            continue
        if state == "conflict" and not args.force:
            conflict_count += 1
            continue
        if not args.dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        if state == "create":
            created += 1
        else:
            overwritten += 1

    mode = "DRY RUN" if args.dry_run else "OK"
    print(
        f"\n{mode} - {created} create, {overwritten} overwrite, "
        f"{identical} unchanged, {conflict_count} conflict; integrations: {', '.join(tools)}"
    )
    return 1 if conflict_count else 0
