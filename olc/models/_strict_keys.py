"""Recursive nested-unknown-key detection for the strict OLC v1 path.

The shared nested models in ``lakelogic.core.models`` are ``extra="allow"`` and
carry important ``mode="before"`` validators. We must NOT flip them to
``extra="forbid"`` (that would change the lenient ``DataContract`` runtime and
break prod). Instead, the strict OLC v1 path overlays a *read-only* check: walk
the incoming dict alongside the model's declared fields and report any nested
key the model does not declare — without disturbing how those models parse.

Free-form regions are never descended into: a field annotated ``Dict[str, Any]``
(or plain ``Any`` / ``dict``) is treated as an opaque bag, so vendor metadata,
compliance blocks, extensions, etc. are left alone.

**Named bags.** A few ``Dict[str, Any]`` fields are not really free-form — they are
a fixed vocabulary the runtime reads by key, kept as a dict only because the runtime
calls ``.get()`` on the value and cannot be handed a model. Those are registered in
:data:`_BAG_SPECS` with their declared key set, so the same strict pass that catches
a misspelled model field also catches a misspelled bag key. Registration is opt-in
per field: every unregistered ``Dict[str, Any]`` stays opaque exactly as before.
"""

from __future__ import annotations

import difflib
import typing
from collections.abc import Iterator, Mapping
from typing import Any

from pydantic import BaseModel

from olc.models._nested import (
    SCD2_KNOWN_KEYS,
    SCD2_UNKNOWN_MEMBER_KNOWN_KEYS,
    Materialization,
)

_NoneType = type(None)


def _unwrap_optional(annotation: Any) -> Any:
    """Strip ``Optional[...]`` / ``T | None`` down to the inner annotation."""
    origin = typing.get_origin(annotation)
    if origin is typing.Union:
        args = [a for a in typing.get_args(annotation) if a is not _NoneType]
        if len(args) == 1:
            return args[0]
    return annotation


def _is_model(tp: Any) -> bool:
    return isinstance(tp, type) and issubclass(tp, BaseModel)


def _iter_child_models(annotation: Any, value: Any) -> Iterator[tuple[dict, type]]:
    """Yield ``(child_dict, child_model_cls)`` reachable from one field value.

    Handles the direct-model, ``List[Model]`` and ``Dict[str, Model]`` shapes.
    Anything else (``Dict[str, Any]``, ``Any``, unions of models, scalars) yields
    nothing — those are opaque and must not be strict-checked.
    """
    ann = _unwrap_optional(annotation)

    if _is_model(ann):
        if isinstance(value, dict):
            yield value, ann
        return

    origin = typing.get_origin(ann)
    args = typing.get_args(ann)

    if origin in (list, typing.List) and args and _is_model(args[0]):
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    yield item, args[0]
        return

    if origin in (dict, typing.Dict) and len(args) == 2 and _is_model(args[1]):
        if isinstance(value, dict):
            for item in value.values():
                if isinstance(item, dict):
                    yield item, args[1]
        return
    # else: opaque (Dict[str, Any], Any, scalar, union-of-models) — skip.


def _alias_strings(alias: Any) -> list[str]:
    """Extract every accepted string key from an alias / AliasChoices / AliasPath."""
    if alias is None:
        return []
    if isinstance(alias, str):
        return [alias]
    # AliasChoices carries a `.choices` list of str | AliasPath; AliasPath (dotted
    # nested access) doesn't name a top-level input key, so only strings count.
    choices = getattr(alias, "choices", None)
    if choices is not None:
        return [c for c in choices if isinstance(c, str)]
    return []


def _accepted_input_keys(model_cls: type[BaseModel]) -> dict[str, Any]:
    """Map every accepted *input* key -> its field annotation (name + aliases).

    Handles plain string aliases as well as ``AliasChoices`` (e.g. the
    deduplicate rule accepts both ``on`` and ``by``) so legitimate aliased keys
    are not mis-flagged as unknown.
    """
    accepted: dict[str, Any] = {}
    for name, field in model_cls.model_fields.items():
        accepted[name] = field.annotation
        for key in _alias_strings(field.alias):
            accepted[key] = field.annotation
        for key in _alias_strings(field.validation_alias):
            accepted[key] = field.annotation
    return accepted


class _BagSpec:
    """The declared key vocabulary of one ``Dict[str, Any]`` field.

    ``children`` maps a known key whose value is itself a keyed bag to that bag's
    spec (e.g. ``scd2.unknown_member``).
    """

    __slots__ = ("known", "children")

    def __init__(
        self,
        known: frozenset,
        children: Mapping[str, "_BagSpec"] | None = None,
    ) -> None:
        self.known = known
        self.children = dict(children or {})


# (owning model, field name) -> declared keys. ONLY these bags are strict-checked.
_BAG_SPECS: dict[tuple[type, str], _BagSpec] = {
    (Materialization, "scd2"): _BagSpec(
        SCD2_KNOWN_KEYS,
        {"unknown_member": _BagSpec(SCD2_UNKNOWN_MEMBER_KNOWN_KEYS)},
    ),
}


def _suggestion(key: str, known: frozenset) -> str:
    """`` (did you mean 'x'?)`` when ``key`` is a near-miss of a declared key."""
    close = difflib.get_close_matches(key, sorted(known), n=1, cutoff=0.7)
    return f" (did you mean '{close[0]}'?)" if close else ""


def _collect_unknown_bag_keys(data: Any, spec: _BagSpec, path: str) -> list[str]:
    """Return dotted paths of keys the bag's declared vocabulary does not contain."""
    if not isinstance(data, dict):
        return []

    unknown: list[str] = []
    for key, value in data.items():
        if key not in spec.known:
            unknown.append(f"{path}{key}{_suggestion(key, spec.known)}")
            continue
        child = spec.children.get(key)
        if child is not None:
            unknown.extend(_collect_unknown_bag_keys(value, child, f"{path}{key}."))
    return unknown


def collect_unknown_nested_keys(
    data: dict, model_cls: type[BaseModel], path: str = ""
) -> list[str]:
    """Return dotted paths of keys not declared by ``model_cls`` (recursively).

    Only descends into nested pydantic models; opaque/free-form regions are left
    untouched. Used by :class:`OLCContractV1` to enforce nested strictness on the
    canonical path without mutating the shared lenient models.
    """
    if not isinstance(data, dict):
        return []

    accepted = _accepted_input_keys(model_cls)
    unknown: list[str] = []

    for key, value in data.items():
        if key not in accepted:
            unknown.append(f"{path}{key}")
            continue
        bag_spec = _BAG_SPECS.get((model_cls, key))
        if bag_spec is not None:
            unknown.extend(_collect_unknown_bag_keys(value, bag_spec, f"{path}{key}."))
        for child_dict, child_cls in _iter_child_models(accepted[key], value):
            unknown.extend(
                collect_unknown_nested_keys(child_dict, child_cls, f"{path}{key}.")
            )

    return unknown
