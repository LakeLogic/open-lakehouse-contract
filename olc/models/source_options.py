"""Typed ``source.options`` — one model per format / source kind, every key described.

``source.options`` used to be a free-form object: a misspelled key (``header_rows``,
``delimeter``) was silently ignored and the load read the wrong row or separator, and no
option appeared in the generated reference, so agents could not use them.

Now the options a source may carry are declared here, selected by the source's ``type``,
``format`` and (for a message broker) ``options.kind``:

==========================================  =======================
source                                      options model
==========================================  =======================
``type: stream`` + ``kind: kafka``          ``KafkaOptions``
``type: stream`` + ``kind: eventhubs``      ``EventHubsOptions``
``type: database``, ``mongodb://`` path     ``MongoDbOptions``
``type: database``, an ``env:`` path         ``DatabaseOptions`` or ``MongoDbOptions``
``type: database``, any other path          ``DatabaseOptions``
``type: sftp``                              ``SftpOptions`` + the file format's options
``format: csv`` / ``tsv``                   ``CsvOptions``
``format: xlsx`` / ``xls`` / ``excel``      ``ExcelOptions``
``format: json`` / ``ndjson`` / ``jsonl``   ``JsonOptions``
``format: xml``                             ``XmlOptions``
``format: fixed_width``                     ``FixedWidthOptions``
``format: avro``                            ``AvroOptions``
``format: parquet``                         ``ParquetOptions``
``format: delta`` / ``iceberg``             ``TableOptions``
document formats (``pdf`` …)                ``DocumentOptions``
no ``format``                               any file format's keys
==========================================  =======================

At runtime ``options`` stays a plain dict (the reference framework reads it by key), so these
models are a strict-path CHECK and the source of the schema and reference — exactly like the
other named bags in ``olc.models._strict_keys``. Every model is closed, except
``engine_options``: engine-specific extras passed through as they are.

**Credentials are never literal.** A key that holds a secret (``password``, ``*_token``,
``*_secret``, ``connection_string`` …) must be an environment reference, ``env:VAR`` or
``${ENV:VAR}``; a literal value is refused with "use a connection secret, not the contract".
"""

from __future__ import annotations

import difflib
import re
from typing import Any, Dict, List, Literal, Optional, Tuple, Type, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError

# ── formats ─────────────────────────────────────────────────────────────────────

#: Every ``source.format`` value, with what it reads. One definition: the schema enum, the
#: reference and the options selection all come from here.
SOURCE_FORMAT_DESCRIPTIONS: Dict[str, str] = {
    "csv": "Delimited text (comma by default; see `delimiter`). `.csv` / `.tsv` files.",
    "tsv": "Tab-separated text: `csv` with a tab delimiter.",
    "json": "JSON: one document per file, or one per line (see `multiline`).",
    "ndjson": "Newline-delimited JSON: one document per line (`.ndjson`).",
    "jsonl": "Same as `ndjson` (`.jsonl`).",
    "xml": "XML: one row per record element (see `row_tag`).",
    "xlsx": "Excel workbook (`.xlsx`).",
    "xls": "Legacy Excel workbook (`.xls`).",
    "excel": "Excel workbook, `.xlsx` or `.xls`.",
    "fixed_width": "Fixed-width text: each field at a fixed position (see `columns` or field `range`).",
    "avro": "Avro container files (`.avro`).",
    "parquet": "Parquet files.",
    "delta": "A Delta table.",
    "iceberg": "An Iceberg table.",
    "pdf": "PDF documents, for `extraction`.",
    "docx": "Word documents, for `extraction`.",
    "pptx": "PowerPoint documents, for `extraction`.",
    "html": "HTML pages, for `extraction`.",
    "image": "Images, for `extraction`.",
}
SOURCE_FORMATS: Tuple[str, ...] = tuple(SOURCE_FORMAT_DESCRIPTIONS)

_ENV_REF = re.compile(
    r"^\s*(env:[A-Za-z_][A-Za-z0-9_]*|\$\{ENV:[A-Za-z_][A-Za-z0-9_]*\})\s*$"
)
_SECRET_NAMES = {
    "password",
    "passwd",
    "secret",
    "token",
    "sas_token",
    "account_key",
    "bearer_token",
    "private_key",
    "client_secret",
    "connection_string",
    "api_key",
    "access_key",
}
_SECRET_SUFFIXES = ("_password", "_secret", "_token", "_key")
#: Keys whose names look secret but hold a non-secret value (a path, a public name).
_NOT_SECRETS = {"private_key_path", "partition_key"}


def is_secret_key(key: str) -> bool:
    """Whether an option NAME holds a credential (its value must be an ``env:`` reference)."""
    k = key.lower()
    if k in _NOT_SECRETS:
        return False
    return k in _SECRET_NAMES or k.endswith(_SECRET_SUFFIXES)


def is_env_reference(value: Any) -> bool:
    return isinstance(value, str) and bool(_ENV_REF.match(value))


_ENGINE_OPTIONS = Field(
    default=None,
    description="Engine-specific extras, passed through as they are and not checked. "
    "The only free-form corner of `options`; prefer a declared key when one exists.",
)
_SECRET_NOTE = (
    " Must be an environment reference (`env:VAR` or `${ENV:VAR}`), never the value."
)


class _Options(BaseModel):
    model_config = ConfigDict(extra="forbid")
    engine_options: Optional[Dict[str, Any]] = _ENGINE_OPTIONS


# ── file formats ────────────────────────────────────────────────────────────────


class _FileOptions(_Options):
    """Keys shared by every file format."""

    archive_member: Optional[str] = Field(
        default=None,
        description="Which members of a `.zip` to read, as a glob, e.g. `orders_*.csv`. "
        "Default: every member with the format's extension (a README is not data). "
        "`.gz` files need no option.",
    )
    implied_decimals: Optional[Dict[str, int]] = Field(
        default=None,
        description="Digits after an implied decimal point, per field, e.g. `{amount: 2}` reads "
        "`12345` as 123.45 (mainframe and BACS layouts).",
    )
    date_formats: Optional[Dict[str, str]] = Field(
        default=None,
        description="Date / timestamp pattern per field, Spark/Java style, e.g. "
        '`{signup_date: yyyyMMdd, paid_at: "dd/MM/yyyy HH:mm:ss"}`. Default: ISO 8601 '
        "(`2026-10-01`, `2026-10-01 09:00:00`, `2026-10-01T09:00:00Z`).",
    )
    decimal_comma: Optional[bool] = Field(
        default=None,
        description="Numbers use a decimal comma and a dot for thousands (`1.234,50` is 1234.5). "
        "Applies to float / double / decimal fields. Default false.",
    )


class CsvOptions(_FileOptions):
    """Options for `format: csv` / `tsv`."""

    delimiter: Optional[str] = Field(
        default=None,
        description="Field separator, one character; `\\t` or `tab` for a tab. Default `,` "
        "(tab for `tsv`).",
    )
    encoding: Optional[str] = Field(
        default=None,
        description="Text encoding, e.g. `utf-8` (default), `latin-1`, `cp1252`, `utf8-lossy` "
        "(replace undecodable bytes instead of failing).",
    )
    skip_rows: Optional[int] = Field(
        default=None, ge=0, description="Lines to skip above the header row. Default 0."
    )
    has_header: Optional[bool] = Field(
        default=None,
        description="Whether the first row (after `skip_rows`) names the columns. Default true; "
        "when false, columns are matched to `model.fields` by position.",
    )
    quote_char: Optional[str] = Field(
        default=None,
        description='Quote character around a field that contains the delimiter. Default `"`.',
    )
    null_values: Optional[List[str]] = Field(
        default=None, description='Strings read as null, e.g. `["", "N/A", "-"]`.'
    )
    comment_prefix: Optional[str] = Field(
        default=None, description="Lines starting with this are skipped, e.g. `#`."
    )


class ExcelOptions(_FileOptions):
    """Options for `format: xlsx` / `xls` / `excel`."""

    sheet_name: Optional[str] = Field(
        default=None,
        description="The sheet (tab) to read, by name. Default: the first sheet. A name the "
        "workbook does not have fails the run.",
    )
    header_row: Optional[int] = Field(
        default=None,
        ge=1,
        description="The row that holds the column names, counting from 1. Default 1; rows above "
        "it are skipped (titles, notes).",
    )
    skip_footer: Optional[int] = Field(
        default=None,
        ge=0,
        description="Rows to drop at the bottom (totals, notes). Default 0.",
    )


class JsonOptions(_FileOptions):
    """Options for `format: json` / `ndjson` / `jsonl`."""

    multiline: Optional[bool] = Field(
        default=None,
        description="true: each file is ONE JSON document (an array or object, possibly over many "
        "lines). false: one document per line. Default: detected from the file.",
    )


class XmlOptions(_FileOptions):
    """Options for `format: xml`."""

    row_tag: Optional[str] = Field(
        default=None,
        description="Element name of one record, matched at any depth, e.g. `order`. Default: the "
        "repeated children of the root element.",
    )


class FixedWidthColumn(BaseModel):
    """One column of a fixed-width layout."""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(description="Column name; matches a `model.fields` name.")
    start: int = Field(ge=1, description="First character position, counting from 1.")
    width: int = Field(ge=1, description="Number of characters.")


class FixedWidthOptions(_FileOptions):
    """Options for `format: fixed_width`."""

    columns: Optional[List[FixedWidthColumn]] = Field(
        default=None,
        description="The layout: `{name, start, width}` per column, `start` counting from 1 as "
        "layout specs do. Alternative to `range` on each model field; wins when both are set.",
    )
    record_length: Optional[int] = Field(
        default=None,
        ge=1,
        description="Fixed record size in characters, for files with no line breaks (mainframe). "
        "A record of a different length is quarantined. Default: one record per line.",
    )
    encoding: Optional[str] = Field(
        default=None,
        description="Text encoding, e.g. `utf-8` (default), `cp037` (EBCDIC), `latin-1`.",
    )
    skip_rows: Optional[int] = Field(
        default=None, ge=0, description="Header records to skip. Default 0."
    )
    skip_footer: Optional[int] = Field(
        default=None, ge=0, description="Trailer records to skip. Default 0."
    )
    strip: Optional[bool] = Field(
        default=None, description="Trim padding spaces from every value. Default true."
    )


class AvroOptions(_FileOptions):
    """Options for `format: avro`. Nested records and arrays arrive as JSON text."""


class ParquetOptions(_FileOptions):
    """Options for `format: parquet`."""


class TableOptions(_Options):
    """Options for `format: delta` / `iceberg`: none yet."""


class DocumentOptions(_Options):
    """Options for document formats read by `extraction` (`pdf`, `docx`, …): none yet."""


# ── connections ─────────────────────────────────────────────────────────────────


class DatabaseOptions(_Options):
    """Options for `type: database` (PostgreSQL, MySQL, SQL Server / Azure SQL, SQLite, …).

    The connection string is `source.path`, normally `env:VAR` so the password stays out of the
    contract."""

    fetch_size: Optional[int] = Field(
        default=None,
        ge=1,
        description="Rows per chunk: the result is read in chunks of this size, so a large table "
        "never has to fit in memory at once. Default: read in one go.",
    )
    partition_column: Optional[str] = Field(
        default=None,
        description="Numeric or date column to split the read on, for a parallel read. Use with "
        "`partition_num`.",
    )
    partition_num: Optional[int] = Field(
        default=None,
        ge=1,
        description="Number of parallel partitions for `partition_column`.",
    )
    partition_lower_bound: Optional[Union[int, float, str]] = Field(
        default=None,
        description="Lowest `partition_column` value. Default: the column's minimum.",
    )
    partition_upper_bound: Optional[Union[int, float, str]] = Field(
        default=None,
        description="Highest `partition_column` value. Default: the column's maximum.",
    )
    cdc_provider: Optional[Literal["azuresql", "azure_sql", "sqlserver", "mssql"]] = (
        Field(
            default=None,
            description="With `load_mode: cdc`: read the database's own change log (inserts, updates "
            "AND deletes) instead of a watermark column. SQL Server / Azure SQL native CDC. Each row "
            "gets `_lakelogic_cdc_op` (insert / update / delete) and `_lakelogic_cdc_ts` (commit time).",
        )
    )
    cdc_capture_instance: Optional[str] = Field(
        default=None,
        description="The CDC capture instance `sys.sp_cdc_enable_table` created, e.g. `dbo_rides`. "
        "Default: `dataset` with `.` replaced by `_`.",
    )


class MongoDbOptions(_Options):
    """Options for `type: database` with a `mongodb://` or `mongodb+srv://` path: MongoDB, Atlas,
    Azure Cosmos DB (MongoDB API), Amazon DocumentDB. `dataset` is the collection."""

    database: Optional[str] = Field(
        default=None,
        description="Database name. Default: the one in the connection string's path.",
    )
    filter: Optional[Dict[str, Any]] = Field(
        default=None,
        description="A MongoDB query document, applied by the server, e.g. `{status: {$ne: test}}`.",
    )
    projection: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Fields to include (1) or leave out (0), e.g. `{items: 0}`.",
    )
    batch_size: Optional[int] = Field(
        default=None,
        ge=1,
        description="Documents fetched per round trip. Default 1000.",
    )


class SftpOptions(_Options):
    """Options for `type: sftp` (`path: sftp://user@host[:port]/dir`), plus the options of the
    file `format` it reads."""

    username: Optional[str] = Field(
        default=None,
        description="Login name, when not in `path`. Default: env `LAKELOGIC_SFTP_USER`.",
    )
    password: Optional[str] = Field(
        default=None,
        description="Login password."
        + _SECRET_NOTE
        + " Default: env `LAKELOGIC_SFTP_PASSWORD`.",
    )
    private_key_path: Optional[str] = Field(
        default=None,
        description="Path to a private key file (key login). Default: env `LAKELOGIC_SFTP_KEY`.",
    )
    known_hosts: Optional[str] = Field(
        default=None,
        description="known_hosts file used to verify the server. Default `~/.ssh/known_hosts`; "
        "an explicit null turns host verification off (not recommended).",
    )


_STARTING_OFFSETS = Field(
    default=None,
    description="Where a FIRST run starts: `earliest` (default) or `latest`. Later runs continue "
    "from the checkpoint.",
)
_CHECKPOINT = Field(
    default=None,
    description="Where the read position is kept. Polars / DuckDB: a SQLite file; Spark: a "
    "folder beside it (`<name>_spark/`). Default `_checkpoints/<dataset>` next to the contract.",
)
_BATCH_SIZE = Field(
    default=None,
    ge=1,
    description="Events per micro-batch (Polars / DuckDB). Default 1000.",
)
_TRIGGER = Field(
    default=None,
    description="`available_now` (default): read everything there now, then stop — for "
    "scheduled jobs. `continuous`: keep running and read new events as they arrive.",
)
_PROCESSING_TIME = Field(
    default=None,
    description="Spark with `trigger: continuous`: how often a micro-batch runs, e.g. "
    "`30 seconds` (default).",
)
_MAX_OFFSETS = Field(
    default=None,
    ge=1,
    description="Spark only: cap on events per micro-batch. Default: no cap.",
)


class KafkaOptions(_Options):
    """Options for `type: stream` with `kind: kafka`: any Kafka-protocol broker (Apache Kafka,
    Confluent, Redpanda, Amazon MSK). Messages must be JSON objects; one that is not is
    quarantined with the reason, and the stream continues."""

    kind: Literal["kafka"] = Field(description="`kafka`.")
    brokers: str = Field(
        description="Broker list `host:port[,host:port]`; a literal or `env:VAR`."
    )
    topic: Optional[str] = Field(
        default=None, description="The topic. Default: `source.path`."
    )
    group_id: Optional[str] = Field(
        default=None,
        description="Consumer group name. Optional: offsets are kept in the checkpoint either way.",
    )
    starting_offsets: Optional[Literal["earliest", "latest"]] = _STARTING_OFFSETS
    checkpoint: Optional[str] = _CHECKPOINT
    batch_size: Optional[int] = _BATCH_SIZE
    trigger: Optional[Literal["available_now", "continuous", "processing_time"]] = (
        _TRIGGER
    )
    processing_time: Optional[str] = _PROCESSING_TIME
    max_offsets_per_trigger: Optional[int] = _MAX_OFFSETS
    security_protocol: Optional[
        Literal["PLAINTEXT", "SSL", "SASL_PLAINTEXT", "SASL_SSL"]
    ] = Field(
        default=None,
        description="How to connect. Default `PLAINTEXT` (a local broker).",
    )
    sasl_mechanism: Optional[Literal["PLAIN", "SCRAM-SHA-256", "SCRAM-SHA-512"]] = (
        Field(
            default=None,
            description="SASL login method. `PLAIN` works on every engine; `SCRAM-SHA-256` / "
            "`SCRAM-SHA-512` on Polars and DuckDB only.",
        )
    )
    sasl_username: Optional[str] = Field(
        default=None, description="SASL user; a literal or `env:VAR`."
    )
    sasl_password: Optional[str] = Field(
        default=None, description="SASL password." + _SECRET_NOTE
    )


class EventHubsOptions(_Options):
    """Options for `type: stream` with `kind: eventhubs`: Azure Event Hubs through its Kafka
    endpoint. The brokers and the SASL login come from the connection string."""

    kind: Literal["eventhubs"] = Field(description="`eventhubs`.")
    connection_string: str = Field(
        description="The Event Hubs namespace connection string." + _SECRET_NOTE
    )
    topic: Optional[str] = Field(
        default=None, description="The event hub name. Default: `source.path`."
    )
    brokers: Optional[str] = Field(
        default=None,
        description="Override of the address taken from the connection string "
        "(`<namespace>.servicebus.windows.net:9093`).",
    )
    group_id: Optional[str] = Field(
        default=None, description="Consumer group name. Optional."
    )
    starting_offsets: Optional[Literal["earliest", "latest"]] = _STARTING_OFFSETS
    checkpoint: Optional[str] = _CHECKPOINT
    batch_size: Optional[int] = _BATCH_SIZE
    trigger: Optional[Literal["available_now", "continuous", "processing_time"]] = (
        _TRIGGER
    )
    processing_time: Optional[str] = _PROCESSING_TIME
    max_offsets_per_trigger: Optional[int] = _MAX_OFFSETS


#: Every options model, in reference order.
OPTIONS_MODELS: Tuple[Type[BaseModel], ...] = (
    CsvOptions,
    ExcelOptions,
    JsonOptions,
    XmlOptions,
    FixedWidthOptions,
    AvroOptions,
    ParquetOptions,
    TableOptions,
    DocumentOptions,
    DatabaseOptions,
    MongoDbOptions,
    SftpOptions,
    KafkaOptions,
    EventHubsOptions,
)

_BY_FORMAT: Dict[str, Type[BaseModel]] = {
    "csv": CsvOptions,
    "tsv": CsvOptions,
    "xlsx": ExcelOptions,
    "xls": ExcelOptions,
    "excel": ExcelOptions,
    "json": JsonOptions,
    "ndjson": JsonOptions,
    "jsonl": JsonOptions,
    "xml": XmlOptions,
    "fixed_width": FixedWidthOptions,
    "avro": AvroOptions,
    "parquet": ParquetOptions,
    "delta": TableOptions,
    "iceberg": TableOptions,
    "pdf": DocumentOptions,
    "docx": DocumentOptions,
    "pptx": DocumentOptions,
    "html": DocumentOptions,
    "image": DocumentOptions,
}
assert set(_BY_FORMAT) == set(SOURCE_FORMATS), "every format needs an options model"

_FILE_MODELS = (
    CsvOptions,
    ExcelOptions,
    JsonOptions,
    XmlOptions,
    FixedWidthOptions,
    AvroOptions,
    ParquetOptions,
)

#: Keys that belong under ``source.options``, not on ``source`` itself.
OPTIONS_ONLY_SOURCE_KEYS = frozenset(
    {"record_length", "encoding", "skip_rows", "skip_footer", "strip"}
)


def _keys(*models: Type[BaseModel]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for m in models:
        for name, f in m.model_fields.items():
            out.setdefault(name, f)
    return out


def options_models_for(source: Dict[str, Any]) -> Tuple[Type[BaseModel], ...]:
    """The options model(s) a source's ``options`` must match (by type, format and kind)."""
    stype = str(source.get("type") or "")
    fmt = str(source.get("format") or "").lower()
    opts = source.get("options") if isinstance(source.get("options"), dict) else {}
    kind = str(opts.get("kind") or "").lower()
    path = str(source.get("path") or "").lower()
    if stype == "stream" and kind == "kafka":
        return (KafkaOptions,)
    if stype == "stream" and kind == "eventhubs":
        return (EventHubsOptions,)
    if stype == "database":
        if path.startswith(("mongodb://", "mongodb+srv://")):
            return (MongoDbOptions,)
        if is_env_reference(source.get("path")):
            # The connection string is only known at run time: SQL or MongoDB keys.
            return (DatabaseOptions, MongoDbOptions)
        return (DatabaseOptions,)
    file_models: Tuple[Type[BaseModel], ...] = (
        (_BY_FORMAT[fmt],) if fmt in _BY_FORMAT else _FILE_MODELS
    )
    if stype == "sftp":
        return (SftpOptions,) + file_models
    return file_models


def check_source_options(source: Dict[str, Any], path: str = "source.") -> List[str]:
    """Problems with ``source.options`` (and options keys placed on ``source``), as messages.

    Empty when the options are valid for the source's type / format / kind."""
    problems: List[str] = []
    for key in OPTIONS_ONLY_SOURCE_KEYS & set(source):
        problems.append(f"{path}{key}: `{key}` belongs under {path}options")
    fmt = source.get("format")
    if fmt is not None and str(fmt).lower() not in _BY_FORMAT:
        close = difflib.get_close_matches(
            str(fmt).lower(), SOURCE_FORMATS, n=1, cutoff=0.6
        )
        hint = f" (did you mean '{close[0]}'?)" if close else ""
        problems.append(
            f"{path}format: '{fmt}' is not a known format{hint}; one of: {', '.join(SOURCE_FORMATS)}"
        )
    opts = source.get("options")
    if opts is None:
        return problems
    if not isinstance(opts, dict):
        return problems + [f"{path}options must be a mapping"]
    if source.get("type") == "stream" and opts.get("kind") not in (
        None,
        "kafka",
        "eventhubs",
    ):
        return problems + [
            f"{path}options.kind: '{opts.get('kind')}' is not one of: kafka, eventhubs"
        ]

    models = options_models_for(source)
    declared = _keys(*models)
    names = (
        " / ".join(m.__name__ for m in models)
        if len(models) <= 2
        else "the file format options"
    )
    for key, value in opts.items():
        if is_secret_key(key) and value is not None and not is_env_reference(value):
            problems.append(
                f"{path}options.{key}: a credential must not be written in the contract — use a "
                f"connection secret: `{key}: env:VAR` (or `${{ENV:VAR}}`)"
            )
        elif key not in declared:
            close = difflib.get_close_matches(key, sorted(declared), n=1, cutoff=0.7)
            hint = f" (did you mean '{close[0]}'?)" if close else ""
            problems.append(f"{path}options.{key}: not an option of {names}{hint}")
    # Value types / ranges / enums, against the first model (or the format's, when one applies).
    if len(models) <= 2:
        for model in models:
            subset = {k: v for k, v in opts.items() if k in model.model_fields}
            try:
                model.model_validate(subset)
            except ValidationError as exc:
                for err in exc.errors():
                    if err["type"] == "missing" and len(models) > 1:
                        continue
                    loc = ".".join(str(p) for p in err["loc"])
                    problems.append(f"{path}options.{loc}: {err['msg']}")
    return problems
