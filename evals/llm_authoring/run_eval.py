"""Exit test for "OLC readable by any LLM" (LakeLogic_SaaS#550).

Asks LLMs to write OLC contracts for the tasks in prompts.yaml, twice each: once with no help,
once with docs/llms.txt in the system prompt. Scores every contract it gets back:

  * PASS  — strictly valid OLC (``olc.models.load_strict``) and no critical or warning finding
            from ``lakelogic lint`` (info findings are allowed)
  * LINT  — valid OLC, but lint reports a critical or warning finding
  * INVALID — not a valid OLC contract (or no YAML in the answer)

    python evals/llm_authoring/run_eval.py --env-file <path to a file with the keys>

The key file holds ``DEEPSEEK_API_KEY=`` and/or ``ANTHROPIC_API_KEY=`` lines (plus
``ANTHROPIC_WORKSPACE_ID=`` when the Anthropic key is not scoped to one workspace); a provider with
no key is skipped. Keys are read into memory only: never printed, logged or written. Results go to
evals/llm_authoring/results/<timestamp>.json (answers included) and a summary to stdout.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from olc.models import load_strict  # noqa: E402
from olc.validate import load_contract_yaml  # noqa: E402

HERE = Path(__file__).resolve().parent
LLMS_TXT = ROOT / "docs" / "llms.txt"

MODELS = {
    "deepseek": {"key": "DEEPSEEK_API_KEY", "model": "deepseek-chat"},
    "claude": {"key": "ANTHROPIC_API_KEY", "model": "claude-sonnet-5-5"},
    # Claude through the Claude Code CLI (`claude -p`), for a machine with Claude Code signed in
    # and no API key. Opt in with --claude-cli.
    "claude-cli": {"key": None, "model": "claude-sonnet-5-5"},
}

#: Set from the key file's ANTHROPIC_WORKSPACE_ID line, when the key needs it.
ANTHROPIC_WORKSPACE_ID = ""

BASE_SYSTEM = (
    "You write Open Lakehouse Contract (OLC) data contracts in YAML. Answer with exactly one "
    "contract in a single ```yaml code block and nothing else."
)


def read_keys(env_file: Path) -> dict[str, str]:
    keys: dict[str, str] = {}
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if value.strip():
            keys[name.strip()] = value.strip()
    return keys


def _post(url: str, headers: dict, body: dict, timeout: int = 180) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed https endpoints
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # The provider's own error message (it never contains the key), so a failure says why.
        raise RuntimeError(
            f"HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:300]}"
        ) from None


def _ask_claude_cli(model: str, system: str, task: str) -> str:
    """One answer from `claude -p`, run in an empty folder so no project files or CLAUDE.md
    reach the model: the system prompt is the only context, as with the API providers."""
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        prompt_file = Path(tmp) / "system.txt"
        prompt_file.write_text(system, encoding="utf-8")
        done = subprocess.run(
            [
                "claude",
                "-p",
                task,
                "--model",
                model,
                "--system-prompt-file",
                str(prompt_file),
                "--output-format",
                "text",
            ],
            cwd=tmp,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=300,
        )
    if done.returncode != 0:
        raise RuntimeError(
            f"claude -p exited {done.returncode}: {done.stderr.strip()[:300]}"
        )
    return done.stdout


def ask(provider: str, key: str, model: str, system: str, task: str) -> str:
    if provider == "claude-cli":
        return _ask_claude_cli(model, system, task)
    if provider == "deepseek":
        data = _post(
            "https://api.deepseek.com/chat/completions",
            {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            {
                "model": model,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": task},
                ],
            },
        )
        return data["choices"][0]["message"]["content"]
    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    if (
        ANTHROPIC_WORKSPACE_ID
    ):  # a key not scoped to one workspace must name the workspace
        headers["anthropic-workspace-id"] = ANTHROPIC_WORKSPACE_ID
    data = _post(
        "https://api.anthropic.com/v1/messages",
        headers,
        {
            "model": model,
            "max_tokens": 4000,
            "system": system,
            "messages": [{"role": "user", "content": task}],
        },
    )
    return "".join(block.get("text", "") for block in data.get("content", []))


def score(answer: str) -> dict:
    """``{"verdict": PASS|LINT|INVALID, "detail": ...}`` for one answer."""
    m = re.search(r"```ya?ml\s*\n(.*?)```", answer, re.S)
    text = m.group(1) if m else answer
    try:
        doc = load_contract_yaml(text)
        load_strict(doc)
    except Exception as exc:  # noqa: BLE001 - any failure to parse or validate is the verdict
        return {"verdict": "INVALID", "detail": str(exc).splitlines()[:4]}
    try:
        from lakelogic.core.contract_lint import review_contract_dict
    except Exception:
        return {"verdict": "PASS", "detail": "lakelogic not installed: lint not run"}
    findings = [
        f
        for f in review_contract_dict(doc, "answer")
        if f.severity in ("critical", "warning")
    ]
    if findings:
        return {
            "verdict": "LINT",
            "detail": [f"{f.check_id}: {f.message[:120]}" for f in findings],
        }
    return {"verdict": "PASS", "detail": []}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env-file", required=True, type=Path)
    ap.add_argument("--only", nargs="*", help="limit to these prompt ids")
    ap.add_argument(
        "--claude-cli",
        action="store_true",
        help="also ask Claude through `claude -p` (no API key)",
    )
    ap.add_argument(
        "--providers", nargs="*", help="limit to these providers, e.g. claude-cli"
    )
    args = ap.parse_args(argv)

    keys = read_keys(args.env_file) if args.env_file.exists() else {}
    global ANTHROPIC_WORKSPACE_ID
    ANTHROPIC_WORKSPACE_ID = keys.get("ANTHROPIC_WORKSPACE_ID", "")
    prompts = yaml.safe_load((HERE / "prompts.yaml").read_text(encoding="utf-8"))
    if args.only:
        prompts = [p for p in prompts if p["id"] in args.only]
    with_docs = (
        BASE_SYSTEM
        + "\n\nThe OLC standard, from its llms.txt:\n\n"
        + LLMS_TXT.read_text(encoding="utf-8")
    )
    conditions = {"no_docs": BASE_SYSTEM, "with_llms_txt": with_docs}

    results = []
    for provider, cfg in MODELS.items():
        if args.providers and provider not in args.providers:
            continue
        if cfg["key"] is None:  # the CLI provider: no key, opt-in only
            if not args.claude_cli:
                continue
            key = ""
        else:
            key = keys.get(cfg["key"])
            if not key:
                print(f"skip {provider}: no {cfg['key']} in the key file")
                continue
        for cond, system in conditions.items():
            for p in prompts:
                try:
                    answer = ask(provider, key, cfg["model"], system, p["task"])
                    verdict = score(answer)
                except Exception as exc:  # noqa: BLE001 - recorded, the run continues
                    answer, verdict = (
                        "",
                        {
                            "verdict": "ERROR",
                            "detail": f"{type(exc).__name__}: {str(exc)[:200]}",
                        },
                    )
                results.append(
                    {
                        "provider": provider,
                        "model": cfg["model"],
                        "condition": cond,
                        "prompt": p["id"],
                        **verdict,
                        "answer": answer,
                    }
                )
                print(f"{provider:9} {cond:14} {p['id']:24} {verdict['verdict']}")

    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    out = (
        out_dir / f"{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print(
        "\nFirst time:            valid OLC  |  fully clean (valid, no critical/warning lint)"
    )
    for provider in MODELS:
        for cond in conditions:
            rows = [
                r
                for r in results
                if r["provider"] == provider and r["condition"] == cond
            ]
            if rows:
                valid = sum(r["verdict"] in ("PASS", "LINT") for r in rows)
                clean = sum(r["verdict"] == "PASS" for r in rows)
                print(
                    f"  {provider:9} {cond:14} {valid}/{len(rows)}  |  {clean}/{len(rows)}"
                )
    print(f"\nanswers and details: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
