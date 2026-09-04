"""Registry documents — ``_domain.yaml`` and ``_system.yaml`` as validatable models.

A contract describes ONE dataset. The two registry files describe the estate the
contracts live in: who owns it, what it costs, how long data is kept, who gets told when
something breaks, what the layers are called, and which contracts belong to which system.
``OLCContractV1`` never modelled them, so until now the only check either file got was
``yaml.safe_load`` — "is this parseable" reported to the user as "valid". A misspelled
``on_events`` token, a channel that routes nowhere, a ``run_log_backend`` typo: all passed.

**Additive by construction.** These are NEW documents. ``OLCContractV1`` is unchanged, so
every existing consumer of the published standard is unaffected.

**Reuse over redefinition.** Where the contract already models a block correctly, these
documents use the same nested type — ``Notification``, ``LineageConfig``,
``Materialization``, ``SchemaPolicy``, ``StrictServer``. A second copy of ``Notification``
here would be exactly the drift these models exist to prevent: two definitions of one
concept, free to disagree. Blocks the contract leaves as ``Dict[str, Any]``
(``compliance``, ``observatory``, ``metadata``) are modelled properly here, because an
untyped bag is where the typos hide.

**Layer maps.** A contract has one ``server`` and one ``materialization``; a system
declares them per layer (``bronze`` / ``silver`` / ``gold``). So those fields are
``Dict[str, <the contract's type>]`` — same value shape, keyed by layer name.

**Lenient parse, strict check** — the contract's own arrangement. The models allow extra
keys (``x-`` vendor blocks are legitimate), and :func:`olc.models.collect_unknown_nested_keys`
overlays the unknown-key report. Validating shape and reporting unknown keys are different
questions and stay separate.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

from olc.models._nested import (
    LineageConfig,
    Materialization,
    Notification,
    Quarantine,
)
from olc.models._nested import PostIngestionConfig, SchemaPolicy
from olc.models._strict_keys import collect_unknown_nested_keys

__all__ = [
    "OLCDomainV1",
    "OLCSystemV1",
    "DomainOwnership",
    "OwnershipContact",
    "DomainSLO",
    "DomainCost",
    "SystemCost",
    "DomainCompliance",
    "DomainObservatory",
    "DomainRetention",
    "RegistryEnvironment",
    "SystemMetadata",
    "SystemStorage",
    "SystemContractEntry",
    "ExternalSource",
    "RegistryQuarantine",
    "LayerServer",
    "LayerPostIngestion",
    "load_strict_domain",
    "load_strict_system",
]


class _Base(BaseModel):
    """Allow extra keys, exactly as the contract's nested models do.

    Vendor blocks (``x-azure-storage``) and forward-compatible additions must not make a
    valid file invalid. Unknown keys are *reported* by the strict overlay rather than
    rejected here.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)


# ── Ownership ─────────────────────────────────────────────────────────────────


class OwnershipContact(_Base):
    """One named human, with the role that says when to wake them."""

    name: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None
    slack: Optional[str] = None


class DomainOwnership(_Base):
    """Who answers for this domain.

    The contract has flat ``info.owner`` / ``info.contact`` strings. A domain needs the
    structure: a team, an escalation list with roles, and the accounting handles
    (``cost_center``, ``jira_project``) that neither belongs on a single dataset nor
    survives being flattened into one string.
    """

    domain_owner: Optional[str] = None
    team: Optional[str] = None
    contacts: List[OwnershipContact] = Field(default_factory=list)
    cost_center: Optional[str] = None
    jira_project: Optional[str] = None


# ── Service levels ────────────────────────────────────────────────────────────


class SLOFreshness(_Base):
    max_delay_minutes: Optional[float] = None
    check_column: Optional[str] = None
    max_source_delay_minutes: Optional[float] = None
    source_check_columns: Optional[List[str]] = None
    source_check_column: Optional[str] = None
    warn_only: Optional[bool] = None


class SLORowCount(_Base):
    min_rows: Optional[int] = None
    max_rows: Optional[int] = None
    anomaly_multiplier: Optional[float] = None
    warn_only: Optional[bool] = None


class SLOQualitySeverity(_Base):
    min_good_ratio: Optional[float] = None
    max_quarantine_ratio: Optional[float] = None


class SLOQuality(_Base):
    """Thresholds — NOT the contract's ``quality`` block.

    The contract's ``quality`` is a rule set (``row_rules`` / ``dataset_rules``). This is
    a pass mark on the outcome of those rules. Same word, two meanings, deliberately kept
    apart: modelling them with one type would let a rule list be accepted where a
    threshold belongs.
    """

    min_good_ratio: Optional[float] = None
    max_quarantine_ratio: Optional[float] = None
    by_severity: Dict[str, SLOQualitySeverity] = Field(default_factory=dict)


class SLOSchedule(_Base):
    expected_start: Optional[str] = None
    expected_end: Optional[str] = None
    timezone: Optional[str] = None
    grace_minutes: Optional[float] = None
    days: Optional[List[str]] = None
    warn_only: Optional[bool] = None


class DomainSLO(_Base):
    """Per-layer or flat service levels for the domain.

    Deliberately NOT the contract's ``ServiceLevel``: that one is
    ``freshness / availability / row_count / completeness``, while a domain declares
    ``freshness / row_count / quality / schedule``. The two overlap on half their fields
    and differ on the other half, so sharing a type would silently accept a field the
    consumer of the other never reads.

    Values may be a layer map (``freshness: {bronze: {...}}``) or a flat block, because
    both forms exist in the wild; the union keeps the file valid either way.
    """

    freshness: Optional[Union[SLOFreshness, Dict[str, SLOFreshness]]] = None
    row_count: Optional[Union[SLORowCount, Dict[str, SLORowCount]]] = None
    quality: Optional[SLOQuality] = None
    schedule: Optional[Union[SLOSchedule, Dict[str, SLOSchedule]]] = None
    availability: Optional[Dict[str, Any]] = None
    completeness: Optional[Dict[str, Any]] = None


# ── Cost ──────────────────────────────────────────────────────────────────────


class CostBudget(_Base):
    daily_limit: Optional[float] = None
    weekly_limit: Optional[float] = None
    monthly_limit: Optional[float] = None
    per_run_anomaly_multiplier: Optional[float] = None
    alert_channels: Optional[List[str]] = None


class CostCluster(_Base):
    min_nodes: Optional[int] = None
    max_nodes: Optional[int] = None
    scaling_assumption: Optional[str] = None


class CostRates(_Base):
    dbu_per_hour: Optional[float] = None
    storage_per_gb_month: Optional[float] = None
    vcpu_hour: Optional[float] = None
    cluster: Optional[CostCluster] = None


class DomainCost(_Base):
    """What the domain is allowed to spend. A budget, not a rate card."""

    currency: Optional[str] = None
    budget: Optional[CostBudget] = None


class SystemCost(_Base):
    """What the system's compute costs. A rate card, not a budget.

    Kept separate from :class:`DomainCost` because they answer different questions and
    share only ``currency``. One type covering both would accept ``budget`` on a rate
    card and ``dbu_per_hour`` on a spending limit.
    """

    currency: Optional[str] = None
    provider: Optional[str] = None
    attribution: Optional[str] = None
    rates: Optional[CostRates] = None
    cluster: Optional[CostCluster] = None
    layer_rates: Dict[str, CostRates] = Field(default_factory=dict)
    budget: Optional[CostBudget] = None


# ── Compliance / retention / observatory ──────────────────────────────────────


class ComplianceFramework(_Base):
    """One regulation's applicability to this domain.

    Written as a MAP (``frameworks: {gdpr: {...}, hipaa: {...}}``), not a list of names:
    a domain has to record that a framework was considered and found not to apply, and a
    list can only say which ones do. "Not applicable, decided" and "never assessed" are
    different states, and the gate reads them differently.
    """

    applicable: Optional[bool] = None
    jurisdiction: Optional[str] = None
    legal_basis: Optional[str] = None
    special_category_data: Optional[bool] = None
    dpia_required: Optional[bool] = None
    notes: Optional[str] = None


class ComplianceProcessor(_Base):
    """A third party the data reaches, and the instrument that permits it."""

    name: Optional[str] = None
    role: Optional[str] = None
    country: Optional[str] = None
    agreement: Optional[str] = None
    mechanism: Optional[str] = None


class ComplianceErasure(_Base):
    strategy: Optional[str] = None
    emit_with_pipeline_metadata: Optional[bool] = None
    subject_id_column: Optional[str] = None


class DomainCompliance(_Base):
    """Modelled, where the contract keeps ``compliance`` as an opaque dict.

    This block drives real gates (residency, DPO review, framework coverage), so a
    misspelled key here fails silently in exactly the place where silence is least
    acceptable.
    """

    sensitivity: Optional[str] = None
    purpose: Optional[Union[str, List[str]]] = None
    risk_level: Optional[str] = None
    risk_triggers: Optional[List[str]] = None
    dpo_review_required: Optional[bool] = None
    frameworks: Optional[Union[Dict[str, ComplianceFramework], List[str]]] = None
    data_residency: Optional[str] = None
    cross_border_transfer: Optional[bool] = None
    transfer_mechanism: Optional[str] = None
    shared_with: Optional[List[Union[ComplianceProcessor, str]]] = None
    erasure: Optional[ComplianceErasure] = None


class DomainRetention(_Base):
    """ISO-8601 durations per layer (``P7D``, ``P90D``, ``P7Y``)."""

    bronze: Optional[str] = None
    silver: Optional[str] = None
    gold: Optional[str] = None


class DomainObservatory(_Base):
    """Telemetry push. ``Dict[str, Any]`` on the contract; typed here.

    ``include_quarantine_sample`` controls rule ATTRIBUTION — which rules failed and how
    often. It carries no source rows and never has.
    """

    enabled: Optional[bool] = None
    endpoint: Optional[str] = None
    api_key: Optional[str] = None
    emit_on: Optional[List[str]] = None
    environments: Optional[List[str]] = None
    layers: Optional[List[str]] = None
    include_quarantine_sample: Optional[bool] = None
    include_schema_snapshot: Optional[bool] = None
    expected_delivery: Optional[Dict[str, Any]] = None
    spool: Optional[Dict[str, Any]] = None


# ── Notifications ─────────────────────────────────────────────────────────────


class NotificationsBlock(_Base):
    """The object form: a switch beside the routes it switches.

    ``notifications`` has been a bare list of channels while the kill switch lived in a
    different file under a different name (``notifications_enabled`` in ``_system.yaml``),
    which is why one reader honoured it and another did not. This form co-locates them,
    matching ``observatory``, where ``enabled`` has always sat inside the block it gates.

    The legacy list form stays valid — see :meth:`OLCDomainV1.notification_channels`.
    """

    enabled: Optional[bool] = None
    channels: List[Notification] = Field(default_factory=list)


# ── System-only blocks ────────────────────────────────────────────────────────


class RegistryEnvironment(_Base):
    """A named environment's roots.

    The contract's ``Environment`` is ``path`` + ``format`` — one dataset's location. A
    system environment carries the roots every contract in it interpolates
    (``{storage_account}``, ``{domain}``), so it is a distinct shape rather than a reuse.
    """

    storage_root: Optional[str] = None
    data_root: Optional[str] = None
    catalog: Optional[str] = None
    storage_account: Optional[str] = None
    quarantine_root: Optional[str] = None
    external_location_root: Optional[str] = None
    path: Optional[str] = None
    format: Optional[str] = None


class SystemMetadata(_Base):
    """Where the pipeline writes its own operational records.

    ``Dict[str, Any]`` on the contract, so a misspelled ``run_log_backend`` validates
    today and the run log lands nowhere.
    """

    run_log_table: Optional[str] = None
    run_log_backend: Optional[str] = None
    slo_checks_table: Optional[str] = None
    slo_checks_backend: Optional[str] = None


class SystemStorage(_Base):
    """Path templates. Values interpolate ``{catalog}``, ``{domain}``, ``{system}``."""

    domain_catalog: Optional[str] = None
    quarantine_root: Optional[str] = None
    external_location_root: Optional[str] = None
    contract_root: Optional[str] = None
    landing_root: Optional[str] = None
    log_root: Optional[str] = None
    landing_path: Optional[str] = None
    contract_path: Optional[str] = None
    archive_path: Optional[str] = None
    log_path: Optional[str] = None
    slo_checks_path: Optional[str] = None
    quarantine_path: Optional[str] = None
    bronze_path: Optional[str] = None
    silver_path: Optional[str] = None
    gold_path: Optional[str] = None


class SystemContractEntry(_Base):
    """One contract in the system's roster.

    Has no contract-side equivalent, and should not: a contract cannot list itself.
    """

    layer: Optional[str] = None
    entity: Optional[str] = None
    path: Optional[str] = None
    enabled: Optional[bool] = None
    depends_on: Optional[List[str]] = None


class ExternalSource(_Base):
    """A source outside the platform.

    Close to the contract's ``UpstreamSource`` but not the same: this adds
    ``source_domain`` and ``consumed_by`` (which contracts read it), and both are the
    reason the block exists at system level. Named ``external_sources`` in the file;
    the contract calls the adjacent idea ``upstream_sources``.
    """

    name: Optional[str] = None
    type: Optional[str] = None
    source_domain: Optional[str] = None
    catalog_path: Optional[str] = None
    path: Optional[str] = None
    format: Optional[str] = None
    owner: Optional[str] = None
    description: Optional[str] = None
    consumed_by: Optional[List[str]] = None


class LayerPostIngestion(PostIngestionConfig):
    """The contract's post-ingestion settings plus the system-only retry flag.

    Subclassed rather than adding the field to ``PostIngestionConfig``: that model is
    part of the contract standard, and widening it would change what a CONTRACT accepts
    to solve a registry problem.
    """

    retry_orphaned_files: Optional[bool] = None


class LayerServer(_Base):
    """Per-layer engine settings on a system.

    NOT the contract's ``StrictServer``, which requires ``path`` — a contract names its
    own location, while a system declares behaviour for every contract in a layer and
    leaves the path to the ``storage`` templates. Reusing the contract type here made
    every real ``_system.yaml`` invalid for want of a field that does not belong in one.
    """

    type: Optional[str] = None
    path: Optional[str] = None
    format: Optional[str] = None
    mode: Optional[str] = None
    cast_to_string: Optional[bool] = None
    schema_policy: Optional[SchemaPolicy] = None
    post_ingestion: Optional[LayerPostIngestion] = None


class RegistryQuarantine(Quarantine):
    """The contract's quarantine plus ``mode``.

    Real ``_system.yaml`` files write ``mode: append`` where the contract models
    ``write_mode``. Both are accepted rather than one being declared wrong, because the
    files predate the model and rejecting them would make a working estate invalid.
    """

    mode: Optional[str] = None


# ── The documents ─────────────────────────────────────────────────────────────


class _RegistryDocument(_Base):
    """Fields shared by both registry files, because ``_system.yaml`` deep-merges over
    ``_domain.yaml`` — anything settable on a domain is overridable on a system."""

    domain: Optional[str] = None
    ownership: Optional[DomainOwnership] = None
    slo: Optional[DomainSLO] = None
    compliance: Optional[DomainCompliance] = None
    observatory: Optional[DomainObservatory] = None
    retention: Optional[DomainRetention] = None
    notifications: Optional[Union[NotificationsBlock, List[Notification]]] = None
    bronze_layer: Optional[str] = None
    silver_layer: Optional[str] = None
    gold_layer: Optional[str] = None

    @field_validator(
        "contracts", "external_sources", "environments", "materialization", "server",
        mode="before",
        check_fields=False,
    )
    @classmethod
    def _declared_but_empty_is_empty(cls, value: Any, info: Any) -> Any:
        """``contracts:`` with nothing under it parses as None, and means "none yet".

        Rejecting that would fail real files for writing a key they have not filled in —
        punishing the more informative form, since omitting the key entirely validates.
        A declared-but-empty block is a statement, not an error.
        """
        if value is not None:
            return value
        return {} if info.field_name in ("environments", "materialization", "server") else []

    def notification_channels(self) -> List[Notification]:
        """The channels, whichever form the file used.

        One reader for two shapes, so a caller never has to ask which it got — the
        question that let the list form and the boolean drift apart in the first place.
        """
        block = self.notifications
        if block is None:
            return []
        if isinstance(block, NotificationsBlock):
            return list(block.channels)
        return list(block)

    def notifications_are_enabled(self) -> bool:
        """Whether routing is on. Absent means on: a file that declares channels and no
        switch means to use them."""
        block = self.notifications
        if isinstance(block, NotificationsBlock) and block.enabled is not None:
            return bool(block.enabled)
        legacy = getattr(self, "notifications_enabled", None)
        return True if legacy is None else bool(legacy)


class OLCDomainV1(_RegistryDocument):
    """``_domain.yaml`` — a domain's ownership, service levels, budget and routing."""

    cost: Optional[DomainCost] = None


class OLCSystemV1(_RegistryDocument):
    """``_system.yaml`` — one system inside a domain: its contracts, storage and engine
    configuration, plus any domain field it overrides."""

    system: Optional[str] = None
    metadata: Optional[SystemMetadata] = None
    storage: Optional[SystemStorage] = None
    contracts: List[SystemContractEntry] = Field(default_factory=list)
    external_sources: List[ExternalSource] = Field(default_factory=list)
    environments: Dict[str, RegistryEnvironment] = Field(default_factory=dict)
    lineage: Optional[LineageConfig] = None
    quarantine: Optional[RegistryQuarantine] = None
    cost: Optional[SystemCost] = None
    # Per layer, unlike a contract's single value — same shape, keyed by layer name.
    materialization: Dict[str, Materialization] = Field(default_factory=dict)
    server: Dict[str, LayerServer] = Field(default_factory=dict)
    # Legacy: the kill switch that belongs inside `notifications`. Kept so existing files
    # validate; `notifications_are_enabled()` still honours it.
    notifications_enabled: Optional[bool] = None


# ── Strict loading ────────────────────────────────────────────────────────────


def _load_strict(document: Any, model_cls: type, kind: str):
    """Validate shape, then report keys the model does not declare.

    Two separate questions, deliberately answered separately — the arrangement the
    contract already uses. The models allow extra keys so a vendor block or a
    forward-compatible addition cannot make a working file invalid; this pass names
    anything undeclared so a TYPO is not silently one of them.

    Both halves are needed. Shape validation alone accepts
    ``slo.quality: {row_rules: [...]}`` — the contract's meaning of ``quality`` written
    where a domain expects thresholds — because the rule list simply rides along as an
    extra key. That is precisely the confusion this file was written to end.
    """
    if not isinstance(document, dict):
        raise ValueError(f"{kind} document must be a mapping, got {type(document).__name__}")
    model = model_cls.model_validate(document)
    unknown = [
        key
        for key in collect_unknown_nested_keys(document, model_cls)
        # `x-` prefixed blocks are the documented vendor-extension escape hatch.
        if not key.split(".")[-1].startswith("x-")
    ]
    if unknown:
        raise ValueError(
            f"{kind} declares keys the standard does not define: {', '.join(sorted(unknown))}"
        )
    return model


def load_strict_domain(document: Any) -> "OLCDomainV1":
    """Validate a ``_domain.yaml`` dict against the standard."""
    return _load_strict(document, OLCDomainV1, "_domain.yaml")


def load_strict_system(document: Any) -> "OLCSystemV1":
    """Validate a ``_system.yaml`` dict against the standard."""
    return _load_strict(document, OLCSystemV1, "_system.yaml")
