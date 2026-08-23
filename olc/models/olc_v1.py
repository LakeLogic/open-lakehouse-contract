"""Strict canonical Open Lakehouse Contract model — v1 (public source of truth).

This is the single, PUBLIC definition of what a valid OLC contract is. The JSON
Schema in ``schema/`` is generated from this model (``scripts/generate_schema.py``),
so an external contributor can regenerate the open standard with **no private
dependency**. The LakeLogic reference runtime consumes this same model.

Constraints live HERE, in Pydantic — root ``extra="forbid"``, SemVer ``version``,
required ``info``/``model``, namespaced ``extensions``, and a corrected ``server``
mode enum. Nested strictness is enforced by ``collect_unknown_nested_keys`` (the
shared nested shapes stay lenient in the runtime; here we overlay a read-only check).
"""

from __future__ import annotations

from typing import Annotated, Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from olc.models._nested import (
    DownstreamConsumer,
    Environment,
    ExternalLogic,
    ExtractionConfig,
    Info,
    LineageConfig,
    Link,
    Materialization,
    Model,
    PostIngestionConfig,
    Quality,
    Quarantine,
    SchemaPolicy,
    ServiceLevel,
    SourceConfig,
    Transformation,
    UpstreamContractRef,
    UpstreamSource,
)
from olc.models._strict_keys import collect_unknown_nested_keys

# Full SemVer 2.0.0 (major.minor.patch with optional -prerelease / +build).
_SEMVER = (
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)

# A namespaced extension key: must contain a separator (`.`, `_`, or `-`).
_EXT_KEY = r"^[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)+$"

SemVer = Annotated[str, StringConstraints(pattern=_SEMVER)]
ExtKey = Annotated[str, StringConstraints(pattern=_EXT_KEY)]


class StrictServer(BaseModel):
    """The `server` block, strict — corrected `mode` enum, no unknown keys.

    Encodes the two real modes a runtime honours (``validate`` / ``ingest``) as a
    ``Literal`` so the value set is enforced by the model, not by prose.
    """

    model_config = ConfigDict(extra="forbid")

    type: Optional[str] = None
    path: str  # Required — the target location (path / URI).
    format: str = "parquet"
    mode: Literal["validate", "ingest"] = "validate"
    cast_to_string: bool = False
    schema_policy: Optional[SchemaPolicy] = None
    post_ingestion: Optional[PostIngestionConfig] = None


class OLCContractV1(BaseModel):
    """Strict canonical OLC contract — the public standard.

    The strictness is encoded directly in the model, so the emitted JSON Schema
    is a faithful projection of it:
      * root ``extra="forbid"`` (no undeclared top-level keys),
      * ``version`` must be SemVer,
      * ``info`` and ``model`` are required,
      * vendor extras go under a namespaced ``extensions`` map,
      * ``server.mode`` is a real enum via :class:`StrictServer`.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _reject_unknown_nested_keys(cls, data: Any) -> Any:
        """Reject nested keys the shared shapes do not declare (read-only)."""
        if isinstance(data, dict):
            unknown = collect_unknown_nested_keys(data, cls)
            if unknown:
                raise ValueError(
                    "unknown key(s) not permitted in canonical OLC contract: "
                    + ", ".join(sorted(unknown))
                )
        return data

    # ── required identity ────────────────────────────────────────────────────
    version: SemVer
    info: Info
    model: Model

    # ── vendor extensions (namespaced) ───────────────────────────────────────
    extensions: Dict[ExtKey, Any] = Field(default_factory=dict)

    # ── everything else the canonical contract may carry ─────────────────────
    metadata: Dict[str, Any] = Field(default_factory=dict)
    server: Optional[StrictServer] = None
    source: Optional[SourceConfig] = None
    environments: Dict[str, Environment] = Field(default_factory=dict)
    links: List[Link] = Field(default_factory=list)
    dataset: Optional[str] = None
    primary_key: List[str] = Field(default_factory=list)
    natural_key: List[str] = Field(default_factory=list)
    lineage: Optional[LineageConfig] = None
    materialization: Optional[Materialization] = None
    logic: Optional[str] = None
    external_logic: Optional[ExternalLogic] = None
    observatory: Optional[Dict[str, Any]] = None
    extraction: Optional[ExtractionConfig] = None
    upstream: List[str] = Field(default_factory=list)
    upstream_contracts: List[UpstreamContractRef] = Field(default_factory=list)
    upstream_sources: List[UpstreamSource] = Field(default_factory=list)
    downstream: List[DownstreamConsumer] = Field(default_factory=list)
    schedule: Optional[str] = None
    schema_policy: Optional[SchemaPolicy] = None
    quality: Optional[Quality] = None
    transformations: List[Transformation] = Field(default_factory=list)
    service_levels: Optional[ServiceLevel] = None
    quarantine: Optional[Quarantine] = None
    compliance: Dict[str, Any] = Field(default_factory=dict)
    tier: Optional[str] = None
    contract_file_name: Optional[str] = None
