"""Standalone Open Lakehouse Contract model shapes (public).

Ported verbatim (field declarations only) from the LakeLogic reference runtime so
the open schema can be regenerated from PUBLIC code with no private dependency.
Runtime validators/methods are intentionally omitted — they do not affect the
emitted JSON Schema. The schema-drift gate proves this port stays faithful.

DO NOT hand-edit piecemeal: keep it a faithful projection of the reference shapes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class Info(BaseModel):
    """Contract metadata such as title, version, and ownership."""

    title: str
    table_name: Optional[str] = None
    version: str = "1.0.0"
    description: Optional[str] = None
    owner: Optional[str] = None
    contact: Optional[Union[str, Dict[str, str]]] = None
    target_layer: Optional[str] = None
    status: Optional[str] = None
    classification: Optional[str] = None
    domain: Optional[str] = None
    system: Optional[str] = None


class SchemaPolicy(BaseModel):
    """Schema enforcement rules for unknown and evolving fields."""

    evolution: Literal[
        "strict", "append", "merge", "overwrite", "compatible", "allow"
    ] = "allow"
    unknown_fields: Literal["quarantine", "drop", "allow"] = "allow"


class PostIngestionConfig(BaseModel):
    """Landing zone lifecycle policy — what to do with source files after
    successful Bronze ingestion.

    Actions:
      delete  — remove source files after commit (zero-retention)
      archive — move source files to archive_path after commit
      retain  — leave source files in place (default / no-op)

    Safety guarantees:
      - Cleanup only executes AFTER a successful Bronze Delta commit.
      - If cleanup fails, the pipeline still succeeds (unless
        cleanup_is_blocking is True).
      - Cleanup failures are logged as warnings for manual intervention.

    Example YAML (system-level default)::

        server:
          bronze:
            post_ingestion:
              action: delete
              cleanup_is_blocking: false

    Example YAML (contract-level with archive)::

        source:
          post_ingestion:
            action: archive
            archive_path: "/archive/crm/customers"
    """

    action: Literal["delete", "archive", "retain"] = "retain"
    cleanup_is_blocking: bool = False
    archive_path: Optional[str] = None


class Environment(BaseModel):
    """Environment-specific path/format overrides."""

    path: str
    format: Optional[str] = None


class SourcePartition(BaseModel):
    """Date-partitioned landing directory configuration.

    Limits file globbing to only the relevant date partitions instead
    of scanning the entire landing directory.

    Example YAML::

        source:
          path: "{landing_root}/events"
          partition:
            format: "y_%Y/m_%m/d_%d"   # strftime tokens
            lookback_days: 3
    """

    model_config = ConfigDict(extra="allow")
    format: str
    lookback_days: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    file_pattern: Optional[str] = None


class DltEndpointConfig(BaseModel):
    """Single REST API endpoint configuration for dlt."""

    model_config = ConfigDict(extra="allow")
    name: str
    path: str
    params: Dict[str, Any] = Field(default_factory=dict)
    paginator: Optional[str] = None


class DltSourceConfig(BaseModel):
    """DLT-specific source configuration, embedded in SourceConfig.

    Supports two modes:

    Mode 1 — Verified Source::

        source:
          type: dlt
          dlt:
            source: stripe_analytics
            resource: charges
            credentials:
              api_key: ${STRIPE_API_KEY}

    Mode 2 — Declarative REST API::

        source:
          type: dlt
          dlt:
            base_url: https://api.example.com/v1/
            credentials:
              api_key: ${API_KEY}
            endpoints:
              - name: users
                path: users
                params:
                  limit: 100
    """

    model_config = ConfigDict(extra="allow")
    source: Optional[str] = None
    resource: Optional[str] = None
    base_url: Optional[str] = None
    endpoints: Optional[List[DltEndpointConfig]] = None
    credentials: Dict[str, str] = Field(default_factory=dict)
    write_disposition: str = "replace"
    max_table_nesting: int = 1


class SourceConfig(BaseModel):
    """Source acquisition settings for landing/stream/table/dlt inputs."""

    model_config = ConfigDict(extra="allow")
    type: str
    query: Optional[str] = None
    path: Optional[str] = None
    format: Optional[str] = None
    options: Optional[Dict[str, Any]] = None
    load_mode: str = "full"
    pattern: Optional[str] = None
    watermark_field: Optional[str] = None
    cdc_op_field: Optional[str] = None
    cdc_delete_values: List[str] = Field(default_factory=list)
    cdc_timestamp_field: Optional[str] = None
    dlt: Optional[DltSourceConfig] = None
    partition: Optional[SourcePartition] = None
    empty_behavior: Optional[Literal["skip", "fail"]] = None
    watermark_strategy: Optional[str] = "max_target"
    target_path: Optional[str] = None
    lookback: Optional[str] = None
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    pipeline_log_table: Optional[str] = None
    pipeline_name: Optional[str] = None
    manifest_path: Optional[str] = None
    watermark_date_parts: Optional[Union[List[str], Dict[str, str]]] = None
    partition_filters: Dict[str, Any] = Field(default_factory=dict)
    flatten_nested: Union[bool, List[str]] = False
    post_ingestion: Optional[PostIngestionConfig] = None
    _SOURCE_KNOWN_KEYS: set = {
        "type",
        "query",
        "path",
        "format",
        "load_mode",
        "pattern",
        "watermark_field",
        "cdc_op_field",
        "cdc_delete_values",
        "cdc_timestamp_field",
        "partition",
        "options",
        "watermark_strategy",
        "target_path",
        "lookback",
        "from_date",
        "to_date",
        "pipeline_log_table",
        "pipeline_name",
        "manifest_path",
        "watermark_date_parts",
        "partition_filters",
        "flatten_nested",
        "dlt",
        "post_ingestion",
    }


class Link(BaseModel):
    """Reference dataset link (file path or table name).

    Load-time subsetting (link only a *portion* of the referenced data):
      • ``columns`` — column projection (load only these columns).
      • ``filter``  — a PORTABLE SQL boolean predicate (WHERE clause) applied at
                      load time on every engine, e.g. ``status = 'active'``. Keeps
                      "one contract, any engine" intact; composes with ``columns``.
      • ``query``   — an ENGINE-SPECIFIC full ``SELECT`` escape hatch for the linked
                      dataset (joins/aggregates/renames at load). Powerful but its
                      SQL dialect may not port across engines — use ``filter`` when
                      portability matters. ``{link}`` refers to the loaded dataset.
    """

    name: str
    path: Optional[str] = None
    type: str = "parquet"
    table: Optional[str] = None
    broadcast: bool = False
    columns: List[str] = Field(default_factory=list)
    filter: Optional[str] = None  # portable SQL WHERE predicate (subset rows at load)
    query: Optional[str] = None  # engine-specific SELECT escape hatch (not portable)


class TransformationRename(BaseModel):
    """Rename a column prior to validation."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")
    from_name: Optional[str] = Field(default=None, alias="from")
    to_name: Optional[str] = Field(default=None, alias="to")
    mappings: Optional[Dict[str, str]] = None


class TransformationDerive(BaseModel):
    """Derive a new field from a SQL expression.

    ``sql`` is the default/Spark expression.  When running on a different
    engine you can supply an engine-specific override:

    * ``sql_duckdb`` — used by the Polars and DuckDB adapters.
    * ``sql_spark`` — explicit Spark override (falls back to ``sql``).
    """

    field: str
    sql: str
    sql_duckdb: Optional[str] = None
    sql_spark: Optional[str] = None


class TransformationLookup(BaseModel):
    """Lookup/join enrichment configuration."""

    field: str
    reference: str
    on: str
    key: str
    value: str
    default_value: Optional[Any] = None


class TransformationFilter(BaseModel):
    """Row-level filter expressed in SQL."""

    sql: str


class TransformationDeduplicate(BaseModel):
    """Deduplication rule configuration.

    ``sort_by`` is REQUIRED. A deduplicate discards rows, so "which duplicate
    survives" is a business decision the contract must state. When it is absent an
    implementation has to invent a survivor — first row read, lexicographically
    smallest, newest file — and every such choice silently destroys data on the
    strength of a rule nobody wrote down. Worse, the choice differs between engines,
    so the same contract yields different tables on different platforms, which is
    precisely what this specification exists to prevent.

    Conformance: OLC-T-002 requires a contract without ``sort_by`` to be REFUSED.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        # `on` accepts the alias `by`, which pydantic cannot express in the emitted
        # `required` list — it drops the field entirely, so a raw JSON-Schema
        # validator would accept a deduplicate with NO key at all. Only pydantic
        # enforced it, meaning the published schema was weaker than the model and
        # any third-party implementation validating against the schema alone would
        # let a keyless dedup through. `anyOf` states the real rule: one spelling or
        # the other must be present.
        json_schema_extra={
            "anyOf": [{"required": ["on"]}, {"required": ["by"]}],
        },
    )
    on: List[str] = Field(validation_alias=AliasChoices("on", "by"))
    sort_by: List[str] = Field(
        min_length=1,
        description=(
            "Columns determining which duplicate survives, applied with `order`. "
            "Required: without it the survivor is undefined and engine-dependent."
        ),
    )
    order: str = "desc"


class TransformationDeduplicateByLatest(BaseModel):
    """DEPRECATED — use ``deduplicate`` with ``sort_by``.

    This shorthand adds no expressiveness: it is exactly
    ``deduplicate(on=key_columns, sort_by=[timestamp_column], order="desc")``, with
    ``order`` pinned so it cannot express "keep the earliest row", "keep the highest
    version", or a multi-column tie-break.

    What it did add was a SECOND spelling of the ordering field —
    ``timestamp_column`` here versus ``sort_by`` there — and authors reliably reach
    for the wrong one on the wrong op, where it is dropped at parse time. One
    operation, one spelling.

    Retained (and still covered by OLC-T-001) because published contracts use it;
    it is no longer recommended anywhere.
    """

    # `extra="allow"` is deliberate ONLY for backward compatibility with contracts
    # already in the wild — do not copy this to new shapes; it silently accepts
    # misspelled fields.
    model_config = ConfigDict(extra="allow")
    key_columns: List[str] = Field(default_factory=list)
    timestamp_column: Optional[str] = None


class TransformationSelect(BaseModel):
    """Select a subset of columns."""

    columns: List[str]


class TransformationDrop(BaseModel):
    """Drop columns by name."""

    columns: List[str]


class TransformationCast(BaseModel):
    """Cast columns to specific types."""

    columns: Dict[str, str]


class TransformationTrim(BaseModel):
    """Trim whitespace from fields."""

    fields: List[str]
    side: str = "both"


class TransformationLower(BaseModel):
    """Lower-case string fields."""

    fields: List[str]


class TransformationUpper(BaseModel):
    """Upper-case string fields."""

    fields: List[str]


class TransformationCoalesce(BaseModel):
    """Coalesce multiple fields into a single output."""

    field: str
    sources: List[str] = Field(default_factory=list)
    default: Optional[Any] = None
    output: Optional[str] = None


class TransformationSplit(BaseModel):
    """Split a string field into an array."""

    field: str
    delimiter: str = ","
    output: Optional[str] = None


class TransformationExplode(BaseModel):
    """Explode an array field into multiple rows."""

    field: str
    output: Optional[str] = None


class TransformationMapValues(BaseModel):
    """Map input values to output values."""

    field: str
    mapping: Dict[str, Any]
    default: Optional[Any] = None
    output: Optional[str] = None


class TransformationRollup(BaseModel):
    """Aggregate data and retain rollup lineage keys."""

    group_by: List[str] = Field(default_factory=list)
    aggregations: Dict[str, str] = Field(default_factory=dict)
    keys: Optional[Union[str, List[str]]] = None
    key_expr: Optional[str] = None
    rollup_keys_column: Optional[str] = "_lakelogic_rollup_keys"
    rollup_keys_count_column: Optional[str] = "_lakelogic_rollup_keys_count"
    upstream_run_id_column: Optional[str] = "_upstream_lakelogic_run_id"
    upstream_run_ids_column: Optional[str] = "_upstream_lakelogic_run_ids"
    distinct: bool = True


class TransformationJoin(BaseModel):
    """Join a reference table to enrich multiple fields."""

    reference: str
    on: str
    key: str
    fields: List[str]
    type: str = "left"
    prefix: Optional[str] = None
    defaults: Dict[str, Any] = Field(default_factory=dict)


class TransformationPivot(BaseModel):
    """Pivot rows into columns using conditional aggregation."""

    model_config = ConfigDict(extra="allow")
    id_vars: List[str] = Field(default_factory=list)
    pivot_col: Optional[str] = None
    pivot_cols: Optional[List[str]] = None
    value_col: Optional[str] = None
    value_cols: Optional[List[str]] = None
    values: List[Any] = Field(default_factory=list)
    pivot_values: Optional[List[Any]] = None
    agg: str = "first"
    aggs: Dict[str, str] = Field(default_factory=dict)
    fill_value: Optional[Any] = None
    separator: str = "_"
    name_template: Optional[str] = None
    value_aliases: Dict[str, str] = Field(default_factory=dict)


class TransformationUnpivot(BaseModel):
    """Unpivot columns into rows."""

    model_config = ConfigDict(extra="allow")
    id_vars: List[str] = Field(default_factory=list)
    value_vars: List[str] = Field(default_factory=list)
    value_cols: Optional[List[str]] = None
    key_field: str = "key"
    value_field: str = "value"
    include_nulls: bool = False
    value_aliases: Dict[str, str] = Field(default_factory=dict)


class TransformationBucketBin(BaseModel):
    """A single range/equality bin for TransformationBucket."""

    label: str
    lt: Optional[float] = None
    lte: Optional[float] = None
    gt: Optional[float] = None
    gte: Optional[float] = None
    eq: Optional[Any] = None


class TransformationBucket(BaseModel):
    """
    Map a numeric (or string) column into labelled bands.

    Compiles to a standard SQL CASE expression — identical across all engines.

    YAML example::

        - phase: post
          bucket:
            field: price_band
            source: pricing_price
            bins:
              - lt: 250000
                label: sub_250k
              - lt: 500000
                label: 250k_500k
              - lt: 1000000
                label: 500k_1m
            default: 1m_plus
    """

    field: str
    source: str
    bins: List[TransformationBucketBin] = Field(default_factory=list)
    default: Optional[Any] = None


class TransformationJsonExtract(BaseModel):
    """
    Extract a scalar value from a JSON string column.

    Engine-agnostic: Polars uses str.json_path_match, DuckDB uses ->> operator,
    Spark uses get_json_object.

    YAML example::

        - phase: post
          json_extract:
            field: location_latitude
            source: location_coordinates
            path: "$.latitude"
            cast: float
    """

    field: str
    source: str
    path: str
    cast: Optional[str] = None


class TransformationDateRangeExplode(BaseModel):
    """
    Explode each row into one row per calendar day in [start_col, end_col].

    The output column receives successive date values. If end_col is omitted
    or null the current date is used as the upper bound.

    Engine-agnostic: Polars uses pl.date_range + explode,
    DuckDB uses generate_series + unnest.

    YAML example::

        - phase: post
          date_range_explode:
            output: snapshot_date
            start_col: creation_date
            end_col: deleted_at       # nullable — defaults to today when null
    """

    output: str
    start_col: str
    end_col: Optional[str] = None
    interval: str = "1d"


class TransformationDateDiff(BaseModel):
    """
    Compute the integer difference between two date/timestamp columns.

    The YAML spec is engine-agnostic; each adapter emits the dialect-correct
    SQL (DATEDIFF, DATE_PART, etc.).

    YAML example::

        - phase: post
          date_diff:
            field: listing_age_days
            from_col: creation_date
            to_col: event_date
            unit: days
    """

    field: str
    from_col: str
    to_col: str
    unit: str = "days"


class Transformation(BaseModel):
    """Transformation step (SQL or structured)."""

    model_config = ConfigDict(extra="allow")
    rename: Optional[TransformationRename] = None
    derive: Optional[TransformationDerive] = None
    lookup: Optional[TransformationLookup] = None
    filter: Optional[TransformationFilter] = None
    deduplicate: Optional[TransformationDeduplicate] = None
    deduplicate_by_latest: Optional[TransformationDeduplicateByLatest] = None
    select: Optional[TransformationSelect] = None
    drop: Optional[TransformationDrop] = None
    cast: Optional[TransformationCast] = None
    trim: Optional[TransformationTrim] = None
    lower: Optional[TransformationLower] = None
    upper: Optional[TransformationUpper] = None
    coalesce: Optional[TransformationCoalesce] = None
    split: Optional[TransformationSplit] = None
    explode: Optional[TransformationExplode] = None
    map_values: Optional[TransformationMapValues] = None
    rollup: Optional[TransformationRollup] = None
    join: Optional[TransformationJoin] = None
    pivot: Optional[TransformationPivot] = None
    unpivot: Optional[TransformationUnpivot] = None
    json_extract: Optional[TransformationJsonExtract] = None
    date_range_explode: Optional[TransformationDateRangeExplode] = None
    bucket: Optional[TransformationBucket] = None
    date_diff: Optional[TransformationDateDiff] = None
    sql: Optional[str] = None
    phase: str = "post"


class RowRuleNotNull(BaseModel):
    """Business-friendly not-null rule."""

    not_null: Union[str, Dict[str, Any], List[Union[str, Dict[str, Any]]]]


class RowRuleAcceptedValues(BaseModel):
    """Business-friendly accepted values rule."""

    accepted_values: Dict[str, Any]


class RowRuleRegexMatch(BaseModel):
    """Business-friendly regex match rule."""

    regex_match: Dict[str, Any]


class RowRuleRange(BaseModel):
    """Business-friendly range rule."""

    range: Dict[str, Any]


class ForeignKeyRef(BaseModel):
    """
    Declaration of a foreign-key relationship on a field.

    Used in two places:
      1. ``FieldDefinition.foreign_key`` — field-level documentation + generator hint.
         The generator samples FK column values from the PK pool of the referenced contract.
      2. ``RowRuleReferentialIntegrity.referential_integrity`` — quality-rule payload
         that the DataProcessor evaluates at validation time.

    Contract YAML example
    ---------------------
    # Field-level (documentation + generator hint)
    schema:
      columns:
        - name: agent_id
          type: BIGINT
          foreign_key:
            contract: silver_agents   # LakeLogic contract name
            column:   agent_id        # PK column in that contract

    # Quality rule (validation)
    quality:
      row_rules:
        - referential_integrity:
            field:    agent_id
            contract: silver_agents
            column:   agent_id
            severity: critical

    dbt equivalent
    ---------------
    - name: agent_id
      tests:
        - relationships:
            to:    ref('agents')
            field: agent_id
    """

    contract: str
    column: str
    severity: str = "error"


class RowRuleReferentialIntegrity(BaseModel):
    """Business-friendly referential integrity rule."""

    referential_integrity: Dict[str, Any]


class RowRuleLifecycleWindow(BaseModel):
    """Business-friendly lifecycle window rule."""

    lifecycle_window: Dict[str, Any]


class DatasetRuleUnique(BaseModel):
    """Business-friendly unique rule."""

    unique: Union[str, List[str], Dict[str, Any]]


class DatasetRuleNullRatio(BaseModel):
    """Business-friendly null ratio rule."""

    null_ratio: Dict[str, Any]


class DatasetRuleRowCountBetween(BaseModel):
    """Business-friendly row count rule."""

    row_count_between: Dict[str, Any]


class QualityRule(BaseModel):
    """Row-level or dataset-level quality rule."""

    name: str
    sql: str
    category: str = "correctness"
    description: Optional[str] = None
    severity: str = "error"
    phase: str = "pre"
    must_be_between: Optional[List[float]] = None
    must_be_less_than: Optional[float] = None
    must_be_greater_than: Optional[float] = None


class Quality(BaseModel):
    """Quality rule groups for row and dataset checks."""

    enforce_required: bool = True
    fail_pipeline_on_dataset_error: bool = False
    row_rules: List[
        Union[
            QualityRule,
            RowRuleNotNull,
            RowRuleAcceptedValues,
            RowRuleRegexMatch,
            RowRuleRange,
            RowRuleReferentialIntegrity,
            RowRuleLifecycleWindow,
        ]
    ] = Field(default_factory=list)
    dataset_rules: List[
        Union[
            QualityRule,
            DatasetRuleUnique,
            DatasetRuleNullRatio,
            DatasetRuleRowCountBetween,
        ]
    ] = Field(default_factory=list)


class Notification(BaseModel):
    """
    Notification channel configuration.

    Minimal usage — just ``target`` and ``on_events``::

        notifications:
          - target: "env:TEAMS_WEBHOOK"
            on_events: [quarantine, failure]

    The ``type`` field defaults to ``apprise`` which auto-detects the
    channel from the target URL scheme (``mailto://``, ``slack://``,
    ``msteams://``, etc.).  Set ``type`` explicitly only when using the
    legacy built-in adapters (``smtp``, ``sendgrid``, ``slack``,
    ``teams``, ``webhook``).
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")
    type: str = "apprise"
    target: Optional[str] = Field(
        default=None, alias=AliasChoices("target", "to", "channel", "url")
    )
    targets: Optional[List[str]] = None
    on_events: List[str] = Field(default_factory=lambda: ["quarantine", "failure"])
    subject_template: Optional[str] = None
    subject_template_file: Optional[str] = None
    message_template: Optional[str] = None
    message_template_file: Optional[str] = None
    body_template: Optional[str] = None
    body_template_file: Optional[str] = None
    template_context: Dict[str, Any] = Field(default_factory=dict)


class Quarantine(BaseModel):
    """Quarantine settings and notification routing."""

    model_config = ConfigDict(extra="allow")
    target: Optional[str] = None
    table: Optional[str] = None
    location: Optional[str] = None
    enabled: bool = True
    include_error_reason: bool = True
    strict_notifications: bool = True
    fail_on_quarantine: bool = False
    notifications_enabled: bool = True
    format: Optional[str] = None
    write_mode: str = "append"
    notifications: List[Notification] = Field(default_factory=list)


class ServiceLevelObjective(BaseModel):
    """Service-level objective definition."""

    description: Optional[str] = None
    threshold: Optional[Union[str, float]] = None
    field: Optional[str] = None


class RowCountSLO(BaseModel):
    """Row count SLO for individual contracts.

    Validates that the output row count falls within expected bounds.
    Checked against the field specified by check_field (default: counts_good).

    When skip_reprocess_days is set and the reprocess date range exceeds that
    threshold, SLO checks and counts_source computation are skipped entirely
    to avoid expensive Spark wide-transformation actions on large backfills.
    """

    min_rows: Optional[int] = None
    max_rows: Optional[int] = None
    check_field: str = "counts_good"
    skip_reprocess_days: int = 3
    description: Optional[str] = None


class ServiceLevel(BaseModel):
    """Service-level settings for freshness, availability, row counts, and
    partition completeness.

    These are four different *units of measurement* and are easy to confuse, so each
    states what it is evaluated against:

    * ``freshness``    — how old the newest record may be (a time delta).
    * ``availability`` — **row-level**. The percentage of ROWS whose ``field`` is
      non-null, evaluated per run against the rows that run actually read. It says
      nothing about whether a file, an interval or a partition ever arrived.
    * ``row_count``    — run-level row-count bounds (see :class:`RowCountSLO`).
    * ``completeness`` — **partition-level**. The fraction of EXPECTED partitions
      that arrived for a partitioned source. It says nothing about the contents of
      the partitions that did arrive.

    ``availability`` and ``completeness`` are the pair most often mistaken for one
    another, and they are independent: a source can deliver every expected partition
    with a wholly null column (completeness 1.0, availability 0.0), or deliver one
    flawless hour out of twenty-four (availability 1.0, completeness ~0.04).
    """

    freshness: Optional[Union[str, ServiceLevelObjective]] = None
    availability: Optional[Union[float, ServiceLevelObjective]] = None
    row_count: Optional[RowCountSLO] = None
    completeness: Optional[Union[float, ServiceLevelObjective]] = Field(
        default=None,
        description=(
            "Partition completeness: the fraction (0.0-1.0) of EXPECTED partitions that "
            "must arrive for a partitioned source. Unlike `availability`, which is "
            "row-level, this is about whether an interval arrived at all -- the hole in "
            "the middle of a series that a check looking only at the newest record "
            "cannot see. "
            "DENOMINATOR: 'expected' means the intervals a seasonal baseline says ALWAYS "
            "deliver -- NOT every interval enumerated in the declared window. A source "
            "with genuinely idle intervals (a rideshare feed at 03:00) can therefore "
            "declare 1.0 and mean it. Were the denominator raw enumeration, every such "
            "contract would be forced to write 0.9 purely to stay quiet, and the number "
            "would stop meaning anything. "
            "GRAIN comes from `source.partition.format` (an `%H` token means hourly); "
            "there is no separate grain field. "
            "This is a COMMITMENT, not monitor tuning. Lookback, minimum history, "
            "tolerance for flaky intervals and alert routing are stateful and temporal, "
            "so they deliberately live in monitor configuration rather than in the "
            "contract, where a schedule change would silently make them wrong."
        ),
    )


class FieldDefinition(BaseModel):
    """Schema field definition."""

    name: str
    type: str
    required: bool = False
    pii: bool = False
    phi: bool = False
    sensitive: bool = False
    classification: Optional[str] = None
    description: Optional[str] = None
    rules: List[QualityRule] = Field(default_factory=list)
    accepted_values: Optional[List[Any]] = None
    min: Optional[float] = None
    max: Optional[float] = None
    foreign_key: Optional[ForeignKeyRef] = None
    nullable: Optional[bool] = None
    milestone: bool = False
    generated: bool = False
    security_groups: List[str] = Field(default_factory=list)
    masking: Optional[str] = None
    masking_format: Optional[str] = None
    pii_vault: Optional[str] = None
    extraction_task: Optional[str] = None
    extraction_examples: List[str] = Field(default_factory=list)
    max_length: Optional[int] = None


class Model(BaseModel):
    """Schema model definition."""

    fields: List[FieldDefinition] = Field(default_factory=list)
    grain: Optional[str] = None
    grain_key: List[str] = Field(default_factory=list)


class FactConfig(BaseModel):
    """
    Kimball Fact Table Automated Governance.

    Automatically injects pipeline constraints based on the defined Fact Table architecture:
    - accumulating_snapshot: ensures milestone dates are monotonically increasing
    - transaction: lock strategy to append
    - factless: asserts no metric columns exist

    YAML example::
        materialization:
          strategy: merge
          fact:
            type: accumulating_snapshot
            milestone_dates:
              - placed_date
              - shipped_date
    """

    type: str
    milestone_dates: List[str] = Field(default_factory=list)


class Materialization(BaseModel):
    """Materialization settings for writing outputs."""

    model_config = ConfigDict(extra="allow")
    strategy: str = "append"
    partition_by: List[str] = Field(default_factory=list)
    cluster_by: List[str] = Field(default_factory=list)
    reprocess_policy: str = "overwrite_partition"
    reprocess_date_column: Optional[str] = None
    target_path: Optional[str] = None
    format: Optional[str] = None
    location: Optional[str] = None
    scd2: Optional[Dict[str, Any]] = None
    fact: Optional[FactConfig] = None
    soft_delete_column: Optional[str] = None
    soft_delete_value: Any = True
    soft_delete_time_column: Optional[str] = None
    soft_delete_reason_column: Optional[str] = None
    table_properties: Optional[Dict[str, str]] = None
    compaction: Optional[Dict[str, Any]] = None
    unknown_member: Optional[Dict[str, Any]] = None
    merge_dedup_guard: Optional[bool] = False
    _MAT_KNOWN_KEYS: set = {
        "strategy",
        "partition_by",
        "cluster_by",
        "reprocess_policy",
        "reprocess_date_column",
        "target_path",
        "format",
        "location",
        "scd2",
        "scd1",
        "fact",
        "soft_delete_column",
        "soft_delete_value",
        "soft_delete_time_column",
        "soft_delete_reason_column",
        "table_properties",
        "compaction",
        "unknown_member",
        "merge_dedup_guard",
        "secondary_targets",
        "dlt_destination",
        "dlt_credentials",
        "dlt_dataset_name",
    }


class UpstreamContractRef(BaseModel):
    """A structured reference to an upstream contract this one depends on.

    Richer sibling of the plain ``upstream: List[str]`` — carries the upstream
    contract's mesh coordinates (layer / domain / system) for end-to-end lineage.
    """

    model_config = ConfigDict(extra="allow")
    contract: str
    layer: Optional[str] = None
    domain: Optional[str] = None
    system: Optional[str] = None
    note: Optional[str] = None


class UpstreamSource(BaseModel):
    """An upstream *origin* of a contract's data that is **not** itself an OLC contract —
    a source system, a landing zone, an external file / API / database / stream, etc.

    This is the upstream mirror of :class:`DownstreamConsumer`: where downstream captures
    consumers with no contract of their own (a BI report reading through a semantic model),
    ``upstream_sources`` captures producers with no contract of their own. It records the
    ingestion provenance the mesh cannot otherwise express — most commonly the
    ``source system → landing zone → bronze`` chain, since neither the source nor the
    landing zone has an OLC file.

    Self-referential: each hop may declare its own ``upstream_sources``, so a bronze
    contract can nest ``landing ← source_system`` end to end. The strict OLC v1 path
    recurses into these and enforces the same key rules.

    Example YAML::

        upstream_sources:
          - type: landing                       # the direct producer of this contract
            name: GA4 app_events landing
            path: "{landing_root}/app_events"
            format: json
            upstream_sources:
              - type: source_system             # where the landing data came from
                name: Google Analytics 4
                system: Google LLC
    """

    model_config = ConfigDict(extra="allow")
    type: str
    name: str
    system: Optional[str] = None  # owning system / vendor (e.g. "Google LLC")
    path: Optional[str] = None  # landing path / source URI
    format: Optional[str] = None
    catalog_path: Optional[str] = None
    owner: Optional[str] = None
    description: Optional[str] = None
    note: Optional[str] = None
    columns_used: List[str] = Field(default_factory=list)
    # Nested origins that feed THIS source (e.g. the source system behind a landing zone).
    upstream_sources: List["UpstreamSource"] = Field(default_factory=list)


# Resolve the self-referential ``upstream_sources`` forward ref above.
UpstreamSource.model_rebuild()


class DownstreamConsumer(BaseModel):
    """
    A downstream consumer of a contract's output.

    Enables end-to-end lineage tracking from source → gold → dashboard/report.
    Declared on gold-layer contracts to capture what uses the data.

    Example YAML:
        downstream:
          - type: dashboard
            name: Monthly Revenue Dashboard
            platform: power_bi
            url: https://app.powerbi.com/groups/.../dashboards/...
            owner: analytics-team
            refresh: "daily 06:00 UTC"

          - type: report
            name: Weekly Sales Report
            platform: databricks_sql

          - type: api
            name: Customer Lookup API
            platform: internal
            url: https://api.internal.com/v1/customers

          - type: ml_model
            name: Churn Prediction
            platform: mlflow
            owner: data-science
    """

    model_config = ConfigDict(extra="allow")
    type: str
    name: str
    platform: Optional[str] = None
    url: Optional[str] = None
    owner: Optional[str] = None
    description: Optional[str] = None
    refresh: Optional[str] = None
    columns_used: List[str] = Field(default_factory=list)
    sla: Optional[str] = None
    managed: Optional[bool] = None
    # Nested consumers that read THROUGH this consumer, capturing multi-hop
    # lineage (e.g. gold table → semantic_model → report). A report nested under
    # a semantic_model consumes the table via that model. Self-referential; the
    # strict OLC v1 path recurses into these and enforces the same key rules.
    consumers: List["DownstreamConsumer"] = Field(default_factory=list)


# Resolve the self-referential ``consumers`` forward ref above.
DownstreamConsumer.model_rebuild()


class ConfidenceConfig(BaseModel):
    """
    Configuration for HOW extraction confidence is scored.

    The confidence THRESHOLD belongs in quality.row_rules, not here::

        quality:
          row_rules:
            - name: confidence_gate
              sql: "_lakelogic_extraction_confidence >= 0.7"
              action: quarantine

    Methods:
      - log_probs: use token-level log probabilities (OpenAI, etc.)
      - self_assessment: ask the LLM to rate its own confidence
      - consistency: run extraction N times, measure field-level agreement
      - field_completeness: % of non-nullable fields that are present
    """

    enabled: bool = True
    method: str = "field_completeness"
    column: str = "_lakelogic_extraction_confidence"
    consistency_runs: int = 3


class RetryConfig(BaseModel):
    """Retry configuration for LLM API calls."""

    max_attempts: int = 3
    backoff: str = "exponential"
    initial_delay: float = 1.0


class PreprocessingConfig(BaseModel):
    """
    Preprocessing pipeline for raw unstructured files before LLM extraction.

    Bronze holds raw files (PDFs, images, videos, audio). Before the LLM
    can extract structured data, we need to convert them to text.

    Example YAML:
        preprocessing:
          content_type: pdf
          ocr:
            enabled: true
            engine: tesseract     # tesseract | azure_di | textract | google_vision
            language: eng
          chunking:
            strategy: page        # page | paragraph | sentence | fixed_size
            max_chunk_tokens: 4000
            overlap_tokens: 200

    For video:
        preprocessing:
          content_type: video
          transcription:
            engine: whisper       # whisper | azure_speech | google_speech
            language: en
          frame_extraction:
            enabled: true
            interval_seconds: 30
            engine: gpt-4o        # vision model for frame analysis
    """

    model_config = ConfigDict(extra="allow")
    content_type: str
    ocr: Optional[Dict[str, Any]] = None
    transcription: Optional[Dict[str, Any]] = None
    frame_extraction: Optional[Dict[str, Any]] = None
    chunking: Optional[Dict[str, Any]] = None
    file_column: Optional[str] = None
    text_output_column: str = "_extracted_text"


class ExtractionConfig(BaseModel):
    """
    LLM extraction configuration for unstructured data processing.

    Turns raw unstructured content (text, PDFs, images, audio, video)
    into structured rows via LLM, governed by the data contract.

    Example YAML:
        extraction:
          provider: openai
          model: gpt-4o-mini
          temperature: 0.1
          prompt_template: |
            Extract the following from this support ticket:
            {{ ticket_body }}
          output_schema:
            - name: sentiment
              type: string
              enum: [positive, neutral, negative]
          source:
            text_column: ticket_body
          confidence:
            min_threshold: 0.8
    """

    model_config = ConfigDict(extra="allow")
    provider: str
    model: str = "auto"
    temperature: float = 0.1
    max_tokens: int = 1000
    response_format: str = "json"
    prompt_template: Optional[str] = None
    system_prompt: Optional[str] = None
    text_column: Optional[str] = None
    context_columns: List[str] = Field(default_factory=list)
    preprocessing: Optional[PreprocessingConfig] = None
    output_schema: List[FieldDefinition] = Field(default_factory=list)
    # provider: regex — deterministic, offline extraction. Maps each output field
    # to a regex with one capture group applied to the text_column. No LLM/network;
    # makes the extraction path testable and conformance-checkable across engines.
    patterns: Optional[Dict[str, str]] = None
    batch_size: int = 50
    concurrency: int = 5
    retry: Optional[RetryConfig] = Field(default_factory=RetryConfig)
    confidence: Optional[ConfidenceConfig] = Field(default_factory=ConfidenceConfig)
    max_cost_per_run: Optional[float] = None
    max_rows_per_run: Optional[int] = None
    fallback_model: Optional[str] = None
    fallback_provider: Optional[str] = None
    redact_pii_before_llm: bool = False
    pii_fields: List[str] = Field(default_factory=list)


class LineageConfig(BaseModel):
    """Lineage capture settings."""

    model_config = ConfigDict(extra="allow")
    enabled: bool = False
    capture_source_path: bool = True
    capture_timestamp: bool = True
    capture_run_id: bool = True
    source_column_name: str = "_lakelogic_source"
    timestamp_column_name: str = "_lakelogic_processed_at"
    run_id_column_name: str = "_lakelogic_run_id"
    capture_contract_name: bool = True
    contract_name_column_name: str = "_lakelogic_contract_name"
    capture_domain: bool = True
    capture_system: bool = True
    domain_column_name: str = "_lakelogic_domain"
    system_column_name: str = "_lakelogic_system"
    capture_created_at: bool = True
    created_at_column_name: str = "_lakelogic_created_at"
    capture_created_by: bool = True
    created_by_column_name: str = "_lakelogic_created_by"
    created_by_override: Optional[str] = None
    preserve_upstream: List[str] = Field(default_factory=list)
    upstream_prefix: str = "_upstream"
    run_id_source: str = "run_id"
    _LINEAGE_KNOWN_KEYS: set = {
        "enabled",
        "capture_source_path",
        "capture_timestamp",
        "capture_run_id",
        "source_column_name",
        "timestamp_column_name",
        "run_id_column_name",
        "capture_contract_name",
        "contract_name_column_name",
        "capture_domain",
        "capture_system",
        "domain_column_name",
        "system_column_name",
        "capture_created_at",
        "created_at_column_name",
        "capture_created_by",
        "created_by_column_name",
        "created_by_override",
        "preserve_upstream",
        "upstream_prefix",
        "run_id_source",
    }


class ExternalLogic(BaseModel):
    """External logic hook for advanced processing.

    ``engine`` is REQUIRED: external logic operates on an engine-specific
    DataFrame, so the engine it runs against must be declared explicitly
    (polars | spark | duckdb | ...) rather than left to an implicit default.
    """

    type: str
    path: str
    engine: str  # required — engine the external logic runs against
    entrypoint: str = "run"
    args: Dict[str, Any] = Field(default_factory=dict)
    output_path: Optional[str] = None
    output_format: Optional[str] = None
    handles_output: Optional[bool] = None
    kernel_name: Optional[str] = None
