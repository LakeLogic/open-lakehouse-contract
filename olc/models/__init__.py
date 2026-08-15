"""Public Open Lakehouse Contract model — the canonical source of the JSON Schema.

The schema in ``schema/`` is generated from ``OLCContractV1`` here, so the open
standard is regenerable from public code alone (no private LakeLogic dependency).

``load_strict`` validates a contract dict against the standard. It does NOT run the
runtime's ODCS/soft-delete normalisation (that convenience lives in the reference
runtime); canonical OLC contracts validate directly.
"""
from __future__ import annotations

from typing import Any

from olc.models._strict_keys import collect_unknown_nested_keys
from olc.models.olc_v1 import OLCContractV1, StrictServer

__all__ = ["OLCContractV1", "StrictServer", "collect_unknown_nested_keys", "load_strict"]


def load_strict(document: Any) -> OLCContractV1:
    """Validate a contract dict against the strict public standard.

    Raises ``pydantic.ValidationError`` / ``ValueError`` if it is not a canonical
    OLC contract.
    """
    return OLCContractV1.model_validate(document)
