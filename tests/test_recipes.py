"""Every Core playbook recipe is a valid OLC contract and declares every value a person sets.

A recipe is what an agent (and LakeLogic's Zeus) copies when asked for a pipeline, so a recipe
that drifts from the schema teaches every agent the wrong shape. Each one must:

* validate as a strict OLC contract once its {parameters} are filled in;
* declare every {parameter} its contract uses, and every env:VAR it reads;
* say, for every parameter, what it is, its expected format and an example;
* never carry a secret value — a secret parameter is an env: / vault reference only.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RECIPES = sorted((ROOT / "recipes").rglob("*.yaml"))
GROUPS = {"ingest", "stream", "land", "deliver", "logic"}
REQUIRED = (
    "id",
    "group",
    "title",
    "when",
    "load_patterns",
    "contract",
    "parameters",
    "before_you_run",
    "studio_test",
    "proven",
)
PARAM_KEYS = ("name", "what", "set_in", "secret", "format", "examples")
PLACEHOLDER = re.compile(r"\{([a-z][a-z0-9_]*)\}")
ENV_REF = re.compile(r"(?:env:|\$\{ENV:)([A-Z][A-Z0-9_]*)")
#: A credential written into a URL (`scheme://user:secret@host`) — never allowed in a contract.
URL_SECRET = re.compile(r"://[^/\s:@{]+:[^@\s/{]+@")


def _strings(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _strings(k)
            yield from _strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)
    elif isinstance(obj, str):
        yield obj


def _filled(obj, values):
    if isinstance(obj, dict):
        return {_filled(k, values): _filled(v, values) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_filled(v, values) for v in obj]
    if isinstance(obj, str):
        return PLACEHOLDER.sub(lambda m: values.get(m.group(1), m.group(0)), obj)
    return obj


class TestRecipes(unittest.TestCase):
    def test_there_are_recipes(self) -> None:
        self.assertTrue(RECIPES, "recipes/ holds no recipe")

    def test_each_recipe_is_complete_and_valid_olc(self) -> None:
        from olc.models import OLCContractV1

        ids = set()
        for path in RECIPES:
            with self.subTest(recipe=path.name):
                r = yaml.safe_load(path.read_text(encoding="utf-8"))
                for key in REQUIRED:
                    self.assertIn(key, r, f"{path.name}: missing {key}")
                self.assertIn(r["group"], GROUPS)
                self.assertNotIn(r["id"], ids, "recipe ids are unique")
                ids.add(r["id"])
                self.assertTrue(
                    str(r["proven"]).strip(), f"{path.name}: not proven by a real run"
                )

                params = {p["name"]: p for p in r["parameters"]}
                for p in r["parameters"]:
                    for key in PARAM_KEYS:
                        self.assertIn(
                            key,
                            p,
                            f"{path.name}: parameter {p.get('name')} has no {key}",
                        )
                    self.assertTrue(
                        p["examples"], f"{path.name}: {p['name']} has no example"
                    )

                text = list(_strings(r["contract"]))
                used = {m for s in text for m in PLACEHOLDER.findall(s)}
                self.assertEqual(
                    used - set(params), set(), f"{path.name}: undeclared placeholders"
                )
                self.assertFalse(
                    [s for s in text if URL_SECRET.search(s)],
                    f"{path.name}: a password in a URL",
                )
                envs = {m for s in text for m in ENV_REF.findall(s)}
                self.assertEqual(
                    envs - set(params), set(), f"{path.name}: undeclared env vars"
                )
                for name in envs:
                    self.assertTrue(
                        params[name]["secret"],
                        f"{path.name}: {name} is read from env but not secret",
                    )

                values = {n: str(params[n]["examples"][0]) for n in used}
                OLCContractV1.model_validate(_filled(r["contract"], values))


if __name__ == "__main__":
    unittest.main()
