"""Read contract YAML the way the runtime reads it.

YAML 1.1 resolves ``on``, ``off``, ``yes`` and ``no`` to booleans. YAML 1.2 does not, and
neither does anyone writing a contract: ``deduplicate: {on: [trip_id]}`` means the column
list, not ``True``.

PyYAML implements 1.1, so ``yaml.safe_load`` turns that key into the boolean ``True`` and
the column list becomes unreachable. The reference runtime already worked around it with a
private loader (``lakelogic/cli/driver.py``) that strips the bool resolver — but every
other reader used plain ``safe_load``, so the SAME FILE parsed two ways:

* the engine deduplicated on ``trip_id``; while
* validators, diffs and revision readers saw ``{True: ['trip_id']}``, silently lost the
  key, and reported a contract that does not exist.

That is the failure this module ends. It belongs in the standard rather than in one
consumer, because "what this document means" is the standard's job to answer — a workaround
living in one repo's CLI is how the two answers appeared in the first place.

Only ``true`` and ``false`` (any case) are booleans here. Everything else stays the string
it was written as.
"""
from __future__ import annotations

import re
from typing import Any, IO, Union

import yaml

__all__ = ["ContractYamlLoader", "safe_load", "safe_load_all"]


class ContractYamlLoader(yaml.SafeLoader):
    """``SafeLoader`` without YAML 1.1's boolean word list."""


def _install_strict_bool_resolver(loader: type) -> None:
    """Drop the inherited bool resolver, then re-add a ``true|false``-only one.

    The resolver map is inherited from ``SafeLoader``, so it must be copied before being
    edited — mutating it in place would reconfigure PyYAML's own loader for the whole
    process, which is exactly the kind of action-at-a-distance this module exists to
    remove.
    """
    loader.yaml_implicit_resolvers = {
        key: [(tag, regexp) for tag, regexp in mappings if tag != "tag:yaml.org,2002:bool"]
        for key, mappings in loader.yaml_implicit_resolvers.items()
    }
    loader.add_implicit_resolver(
        "tag:yaml.org,2002:bool",
        re.compile(r"^(?:true|false)$", re.IGNORECASE),
        list("tTfF"),
    )


_install_strict_bool_resolver(ContractYamlLoader)


def safe_load(stream: Union[str, bytes, IO[str], IO[bytes]]) -> Any:
    """``yaml.safe_load`` with YAML 1.1's boolean words left as strings.

    Use this for any contract or registry document. ``yaml.safe_load`` is safe in the
    security sense and wrong in the semantic one: it silently rewrites ``on:``.
    """
    return yaml.load(stream, Loader=ContractYamlLoader)


def safe_load_all(stream: Union[str, bytes, IO[str], IO[bytes]]):
    """Multi-document variant of :func:`safe_load`."""
    return yaml.load_all(stream, Loader=ContractYamlLoader)
