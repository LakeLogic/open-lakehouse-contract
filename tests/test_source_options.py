"""Typed source.options: every option declared and described, selected by type / format / kind.

Before 0.21 `source.options` was free-form: a misspelled key was silently ignored (the load
read the wrong row or separator), and no option reached the generated reference.
"""

import pytest
from pydantic import BaseModel

from olc.models.olc_v1 import OLCContractV1
from olc.models.source_options import (
    OPTIONS_MODELS,
    SOURCE_FORMAT_DESCRIPTIONS,
    check_source_options,
    options_models_for,
)

BASE = {"version": "1.0.0", "info": {"title": "t"}, "model": {"fields": [{"name": "a", "type": "string"}]}}


def _problems(source):
    return check_source_options(source)


def _valid(source):
    OLCContractV1.model_validate({**BASE, "source": source})


def test_a_misspelled_option_fails_with_a_suggestion():  # acceptance 1
    [msg] = _problems({"type": "landing", "path": "x", "format": "xlsx", "options": {"header_rows": 2}})
    assert "header_rows" in msg and "did you mean 'header_row'" in msg
    with pytest.raises(ValueError, match="header_row"):
        _valid({"type": "landing", "path": "x", "format": "xlsx", "options": {"header_rows": 2}})


def test_a_literal_credential_is_refused_and_an_env_reference_is_not():  # acceptance 3
    src = {"type": "sftp", "path": "sftp://h/in", "format": "csv"}
    for key in ("password", "sas_token", "client_secret"):
        [msg] = [p for p in _problems({**src, "options": {key: "hunter2"}}) if key in p]
        assert "connection secret" in msg
    assert _problems({**src, "options": {"password": "env:SFTP_PASSWORD"}}) == []
    assert _problems({**src, "options": {"password": "${ENV:SFTP_PASSWORD}"}}) == []


def test_fixed_width_keys_on_source_are_moved_by_the_message():  # acceptance 9
    [msg] = _problems({"type": "landing", "path": "x", "format": "fixed_width", "record_length": 80})
    assert msg == "source.record_length: `record_length` belongs under source.options"
    _valid({"type": "landing", "path": "x", "format": "fixed_width", "options": {"record_length": 80}})


def test_an_unknown_format_is_refused_with_a_suggestion():
    [msg] = _problems({"type": "landing", "path": "x", "format": "cvs"})
    assert "did you mean 'csv'" in msg


def test_values_are_checked_not_just_keys():
    [msg] = _problems({"type": "stream", "options": {"kind": "kafka", "brokers": "b:9092", "trigger": "nightly"}})
    assert "options.trigger" in msg
    [msg] = _problems({"type": "landing", "path": "x", "format": "xlsx", "options": {"header_row": 0}})
    assert "header_row" in msg


@pytest.mark.parametrize(
    "source, model",
    [
        ({"type": "stream", "options": {"kind": "kafka"}}, "KafkaOptions"),
        ({"type": "stream", "options": {"kind": "eventhubs"}}, "EventHubsOptions"),
        ({"type": "database", "path": "mongodb+srv://c/db"}, "MongoDbOptions"),
        ({"type": "database", "path": "env:PG"}, "DatabaseOptions"),
        ({"type": "landing", "format": "csv"}, "CsvOptions"),
        ({"type": "landing", "format": "fixed_width"}, "FixedWidthOptions"),
    ],
)
def test_the_options_model_follows_type_format_and_kind(source, model):
    assert options_models_for(source)[0].__name__ == model


def test_sftp_accepts_its_own_keys_and_the_formats():
    assert _problems({"type": "sftp", "path": "sftp://h/in", "format": "csv",
                      "options": {"username": "u", "known_hosts": "/k", "delimiter": ";"}}) == []


def test_the_example_contracts_shapes_are_valid():
    # The shapes shipped in lakelogic/examples (streaming + databases contracts).
    _valid({"type": "stream", "options": {"kind": "kafka", "brokers": "env:KAFKA_BROKERS", "topic": "rides",
            "starting_offsets": "earliest", "checkpoint": "data/c.sqlite", "batch_size": 100,
            "trigger": "available_now"}})
    _valid({"type": "stream", "options": {"kind": "eventhubs", "connection_string": "env:EH", "topic": "rides"}})
    _valid({"type": "database", "path": "env:AZURE_SQL_URI", "load_mode": "cdc",
            "options": {"cdc_provider": "azuresql", "cdc_capture_instance": "dbo_rides"}})
    _valid({"type": "database", "path": "env:MONGO_URI", "options": {"database": "d", "filter": {"status": {"$ne": "x"}}}})


def _fields(model: type[BaseModel]):
    for name, f in model.model_fields.items():
        yield model, name, f
        ann = getattr(f.annotation, "__args__", ()) or ()
        for inner in ann:
            for sub in getattr(inner, "__args__", ()) or (inner,):
                if isinstance(sub, type) and issubclass(sub, BaseModel):
                    yield from _fields(sub)


def test_every_option_and_format_is_described():  # spec part 3, for the options
    missing = [f"{m.__name__}.{n}" for model in OPTIONS_MODELS for m, n, f in _fields(model)
               if not (f.description or "").strip()]
    assert missing == [], f"options without a description: {missing}"
    assert all(d.strip() for d in SOURCE_FORMAT_DESCRIPTIONS.values())
