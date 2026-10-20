"""Contract-level compliance blocks that OLC models (the rest of ``compliance`` stays open).

``compliance`` is a free-form map on the contract: the runtime reads it by key, and
existing contracts carry their own entries there (``erasure``, ``strategy`` …). One entry
is modelled because a misspelling in it fails silently in the worst place:

``compliance.retention`` — how long THIS dataset's records may be kept, and what measures
a record's age. It overrides the domain's per-layer period (``registry_v1.DomainRetention``)
for this contract only, so personal data can be held to a different period than the rest
of its layer (driver records six years, trips ninety days).

Precedence, for every reader: ``compliance.retention.period`` on the contract, else the
domain's period for the contract's layer, else no promise.

Compatibility: the docs have shown ``retention: { period: 400d, basis: legal }`` since the
block was free-form, so that shape stays valid — the short ``400d`` / ``6y`` form is
accepted beside ISO 8601, and :func:`iso_period` turns either into ISO for a reader.
"""

from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: ISO 8601 (``P90D``, ``P6Y``, ``P1Y6M``, ``PT12H``) or the short form the docs have always
#: shown (``400d``, ``12w``, ``18m``, ``6y``). No look-ahead: the schema's regex engine has
#: none, so ``P`` / ``PT`` alone are refused by the validator below.
RETENTION_PERIOD = r"^(P(\d+Y)?(\d+M)?(\d+W)?(\d+D)?(T(\d+H)?(\d+M)?(\d+S)?)?|\d+[dDwWmMyY])$"

#: When the retention clock starts. A record's creation is the common case; many
#: obligations run from the END of a relationship (six years after an account closes),
#: which a creation date cannot measure — say so rather than measure the wrong thing.
RETENTION_STARTS = ("record_created", "relationship_ended", "custom")

_SHORT = re.compile(r"^(\d+)([dwmy])$", re.I)


def iso_period(period: str) -> str:
    """``400d`` → ``P400D``, ``6y`` → ``P6Y``; an ISO period is returned as given."""
    m = _SHORT.match(period.strip())
    return f"P{m.group(1)}{m.group(2).upper()}" if m else period.strip()


class ContractRetention(BaseModel):
    """``compliance.retention`` on a contract."""

    model_config = ConfigDict(extra="forbid")

    period: str = Field(
        pattern=RETENTION_PERIOD,
        description="How long a record may be kept: ISO 8601 (P90D, P6Y, P1Y6M) or the short "
        "form (400d, 6y). Overrides the domain's retention for this contract's layer.",
    )
    column: Optional[str] = Field(
        default=None,
        description="The column whose OLDEST value measures a record's age (e.g. signup_date). "
        "Omitted: the runtime's default age columns.",
    )
    starts: Optional[Literal["record_created", "relationship_ended", "custom"]] = Field(
        default=None,
        description="When the retention clock starts: record_created, relationship_ended "
        "(e.g. six years after an account closes), or custom (explain in `basis`).",
    )
    basis: Optional[str] = Field(
        default=None,
        description="Why this period applies (e.g. legal, contract, 'Tax: 6 years from signup').",
    )

    @field_validator("period")
    @classmethod
    def _period_has_a_length(cls, v: str) -> str:
        if v in ("P", "PT") or v.endswith("T"):
            raise ValueError(f"{v!r} is not a duration: give at least one amount, e.g. P90D or P6Y")
        return v
