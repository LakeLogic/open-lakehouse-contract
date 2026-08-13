"""`olc init` — install OLC agent integrations into a project.

Mirrors OpenSpec's approach: one common set of verbs, per-assistant wrapper files
installed into the tool's native location. Open and runtime-free — pure file copy.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
SKILLS = PKG_ROOT / "skills"

# tool -> [(source under skills/, destination under the project root)]
INSTALLERS: dict[str, list[tuple[str, str]]] = {
    "claude": [
        ("claude/commands", ".claude/commands"),   # slash commands
        ("claude/skills", ".claude/skills"),        # Agent Skill
    ],
    "codex": [
        ("codex/prompts", ".codex/prompts"),        # custom prompts
    ],
    "cursor": [
        ("cursor/rules", ".cursor/rules"),          # project rule (.mdc)
    ],
    "copilot": [
        ("copilot", ".github"),                     # .github/copilot-instructions.md
    ],
    "gemini": [
        ("gemini/root", "."),                       # GEMINI.md
        ("gemini/commands", ".gemini/commands"),    # TOML slash commands
    ],
    "windsurf": [
        ("windsurf/rules", ".windsurf/rules"),      # rule (.md)
    ],
    "cline": [
        ("cline", ".clinerules"),                   # .clinerules/*.md
    ],
    "agents": [
        ("agents", "."),                            # AGENTS.md (shared standard: OpenCode, Q, Jules, Zed, …)
    ],
    "amazonq": [
        ("amazonq/rules", ".amazonq/rules"),        # Amazon Q Developer rule
    ],
    "roo": [
        ("roo/rules", ".roo/rules"),                # Roo Code rule
    ],
    "kilocode": [
        ("kilocode/rules", ".kilocode/rules"),      # Kilo Code rule
    ],
}


def _copy_tree(src: Path, dst: Path, log) -> int:
    n = 0
    for f in sorted(src.rglob("*")):
        if f.is_file():
            out = dst / f.relative_to(src)
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, out)
            log(f"    + {out}")
            n += 1
    return n


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="olc init", description="Install OLC agent integrations.")
    ap.add_argument("--tools", default="claude",
                    help="comma-separated: claude,codex,cursor,copilot,gemini,windsurf,cline — or 'all'")
    ap.add_argument("--dest", default=".", help="project root to install into (default: .)")
    ap.add_argument("--list", action="store_true", help="list available integrations and exit")
    args = ap.parse_args(argv)

    if args.list:
        print("Available OLC agent integrations:")
        for t in INSTALLERS:
            print(f"  - {t}")
        print("  (use --tools all to install every one)")
        return 0

    dest = Path(args.dest).resolve()
    tools = [t.strip() for t in args.tools.split(",") if t.strip()]
    if "all" in tools:
        tools = list(INSTALLERS)
    total = 0
    for tool in tools:
        specs = INSTALLERS.get(tool)
        if not specs:
            print(f"[skip] {tool}: no template yet (available: {', '.join(INSTALLERS)}).")
            continue
        print(f"Installing OLC integration for '{tool}' -> {dest}")
        for sub, ddst in specs:
            src = SKILLS / sub
            if src.exists():
                total += _copy_tree(src, dest / ddst, print)

    if total:
        print(f"\nOK - installed {total} file(s) for: {', '.join(tools)}.")
        if "claude" in tools:
            print("In Claude Code:  /olc:validate  |  /olc:contract \"<intent>\"  |  /olc:review")
        if "gemini" in tools:
            print("In Gemini CLI:   /olc:validate  |  /olc:contract \"<intent>\"  |  /olc:review")
        if "codex" in tools:
            print("In Codex, the same verbs are available as prompts (/olc-validate, ...).")
        if {"cursor", "copilot", "windsurf", "cline"} & set(tools):
            print("Cursor / Copilot / Windsurf / Cline: the OLC rules load automatically for *.olc.yaml.")
    else:
        print("Nothing installed.")
    return 0
