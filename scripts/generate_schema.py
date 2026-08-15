"""Regenerate the Open Lakehouse Contract JSON Schema from the reference model.

The OLC spec is not hand-maintained — it is *generated* from the **public** strict
``OLCContractV1`` Pydantic model (``olc.models``, in this repository) plus a small set
of **documented** post-processing steps (see below): nested-object closing, validation-
alias mirroring, and the dataset-rule ``name`` shim. So the schema is a faithful
projection of the model, not purely the raw Pydantic emission — and the schema-drift
gate (``tests/test_schema_drift.py``) guarantees the committed schema always equals
this generator's output. Because the model lives here, anyone can regenerate the open
schema with no private dependency:

    pip install -e .[models]
    python scripts/generate_schema.py

Why the strict ``OLCContractV1`` (not a lenient runtime model):
    ``OLCContractV1`` is the *public standard* — it encodes the strict rules
    (root ``extra="forbid"``, SemVer ``version``, required ``info``/``model``,
    namespaced ``extensions``) directly in Pydantic, so those constraints are
    emitted into the schema for free instead of being bolted on afterwards. A
    reference framework's *runtime* model may be deliberately more permissive
    (``extra="allow"``) to carry runtime-only affordances; the standard stays
    strict. This is what closes the "schema disagrees with the model" gap: the
    schema is a faithful projection of the model that actually enforces it.

The one transform still applied post-emit is nested-object closing
(``_close_nested_objects``). It is the JSON-Schema mirror of the model-side
``collect_unknown_nested_keys`` validator: the ~30 *shared* nested models remain
``extra="allow"`` (flipping them changes the lenient runtime — a separate,
breaking migration), so their strictness cannot yet be expressed natively in the
emitted schema. Once those models are flipped, this step becomes removable too.
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from olc.models import OLCContractV1  # the canonical public standard  # noqa: E402
from olc.models import _nested as _models  # noqa: E402

OUT = (
    Path(__file__).resolve().parents[1]
    / "schema"
    / "open-lakehouse-contract.schema.json"
)
SCHEMA_URI = "https://json-schema.org/draft/2020-12/schema"
ID = "https://lakelogic.org/open-lakehouse-contract/v1/schema.json"


def _close_nested_objects(node: object) -> None:
    """Reject invented keys on every object with a declared property set.

    Mirror of the model-side ``collect_unknown_nested_keys`` validator. Free-form
    mapping fields use ``additionalProperties`` / ``patternProperties`` *without*
    a ``properties`` block and deliberately stay open (vendor metadata,
    extensions, config maps); everything with a declared shape is closed so
    misspelled OLC vocabulary fails structural validation.

    The root object and ``extra="forbid"`` sub-models (e.g. ``StrictServer``)
    already carry ``additionalProperties: false`` straight from the model — this
    only fills in the shared nested models that are still ``extra="allow"``.
    """
    if isinstance(node, dict):
        if node.get("type") == "object":
            if isinstance(node.get("properties"), dict):
                node["additionalProperties"] = False
            elif (
                isinstance(node.get("patternProperties"), dict)
                and len(node["patternProperties"]) == 1
                and "propertyNames" not in node
            ):
                # Constrained-key map (e.g. `extensions` from Dict[ExtKey, Any]):
                # pydantic emits `patternProperties`, which only constrains the
                # *values* of matching keys and lets non-matching keys through.
                # Convert it to `propertyNames` (the pattern still comes from the
                # model) so EVERY key must be namespaced — matching the model,
                # which rejects unnamespaced keys — while values stay open.
                pattern = next(iter(node["patternProperties"]))
                node.pop("patternProperties")
                node["propertyNames"] = {"pattern": pattern}
                node.setdefault("additionalProperties", True)
        for value in node.values():
            _close_nested_objects(value)
    elif isinstance(node, list):
        for value in node:
            _close_nested_objects(value)


def _declare_dataset_rule_names(schema: dict) -> None:
    """Make the shorthand dataset-rule ``name`` key explicit before closing.

    OLC examples give shorthand dataset rules a human-readable ``name``. The
    shared Pydantic models historically accepted it via ``extra="allow"`` without
    declaring it; declare it so it survives ``_close_nested_objects``.
    """
    for definition_name, definition in schema.get("$defs", {}).items():
        if definition_name.startswith("DatasetRule") and isinstance(
            definition.get("properties"), dict
        ):
            definition["properties"].setdefault(
                "name",
                {
                    "title": "Name",
                    "description": "Stable human-readable identifier for the dataset rule.",
                    "type": "string",
                    "minLength": 1,
                },
            )


def _mirror_validation_aliases(schema: dict) -> None:
    """Emit every ``AliasChoices`` key the models accept as a schema property.

    Pydantic emits a field with ``validation_alias=AliasChoices("on", "by")`` as a
    single property (``on``); the model still accepts ``by``. Left alone, closing
    the object would reject ``by`` even though the model accepts it. Mirror all
    string alias choices into the ``$def`` (copying the canonical property's
    subschema) and relax ``required`` for those fields, so the schema accepts
    exactly what the model does. Runs BEFORE nested-closing.
    """
    defs = schema.get("$defs", {})
    for _n, cls in inspect.getmembers(
        _models, lambda o: isinstance(o, type) and issubclass(o, BaseModel)
    ):
        definition = defs.get(cls.__name__)
        if not isinstance(definition, dict) or "properties" not in definition:
            continue
        props = definition["properties"]
        for fname, field in cls.model_fields.items():
            choices = getattr(field.validation_alias, "choices", None)
            if not choices:
                continue
            prop_key = field.alias if isinstance(field.alias, str) else fname
            base = props.get(prop_key)
            if base is None:
                for choice in choices:
                    if isinstance(choice, str) and choice in props:
                        base = props[choice]
                        break
            if base is None:
                continue
            for choice in choices:
                if isinstance(choice, str):
                    props.setdefault(choice, base)
            # JSON Schema `required` can't say "one of these alias keys", so drop
            # the field from required; the model still enforces its presence.
            if (
                isinstance(definition.get("required"), list)
                and prop_key in definition["required"]
            ):
                definition["required"] = [
                    r for r in definition["required"] if r != prop_key
                ]


def build_schema() -> dict:
    """Build the OLC JSON Schema dict from the model (no file write).

    Exposed so the schema-drift test can regenerate in-memory and compare against
    the committed file without touching disk.
    """
    # Root strictness, SemVer `version`, required [version, info, model], and the
    # namespaced `extensions` map all come straight from OLCContractV1 now.
    schema = OLCContractV1.model_json_schema()
    schema = {
        "$schema": SCHEMA_URI,
        "$id": ID,
        "title": "Open Lakehouse Contract",
        **schema,
    }

    # Nested strictness for the still-lenient shared models (mirror of the
    # model-side collect_unknown_nested_keys validator).
    _declare_dataset_rule_names(schema)
    _mirror_validation_aliases(schema)  # before closing: accept aliased keys (on/by)
    _close_nested_objects(schema)
    return schema


def render_schema(schema: dict) -> str:
    """Canonical on-disk rendering of the schema (single source of formatting)."""
    return json.dumps(schema, indent=2) + "\n"


def main() -> None:
    schema = build_schema()
    OUT.write_text(render_schema(schema), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(OUT.parents[1])}")
    print(f"  top-level fields : {len(schema.get('properties', {}))}")
    print(f"  nested models    : {len(schema.get('$defs', {}))}")
    print(f"  root required    : {schema.get('required')}")
    print(
        f"  root closed      : additionalProperties={schema.get('additionalProperties')}"
    )


if __name__ == "__main__":
    main()
