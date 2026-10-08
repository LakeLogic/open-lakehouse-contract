"""Typed source.options: every option declared and described, selected by type / format / kind.

Before 0.21 `source.options` was free-form: a misspelled key was silently ignored (the load
read the wrong row or separator), and no option reached the generated reference.
"""

import unittest

from pydantic import BaseModel

from olc.models.olc_v1 import OLCContractV1
from olc.models.source_options import (
    OPTIONS_MODELS,
    SOURCE_FORMAT_DESCRIPTIONS,
    check_source_options,
    options_models_for,
)

BASE = {"version": "1.0.0", "info": {"title": "t"}, "model": {"fields": [{"name": "a", "type": "string"}]}}


def _valid(source):
    OLCContractV1.model_validate({**BASE, "source": source})


def _fields(model):
    for name, f in model.model_fields.items():
        yield model, name, f
        for inner in getattr(f.annotation, "__args__", ()) or ():
            for sub in getattr(inner, "__args__", ()) or (inner,):
                if isinstance(sub, type) and issubclass(sub, BaseModel):
                    yield from _fields(sub)


class SourceOptionsTests(unittest.TestCase):
    def test_a_misspelled_option_fails_with_a_suggestion(self):  # acceptance 1
        src = {"type": "landing", "path": "x", "format": "xlsx", "options": {"header_rows": 2}}
        [msg] = check_source_options(src)
        self.assertIn("did you mean 'header_row'", msg)
        with self.assertRaisesRegex(ValueError, "header_row"):
            _valid(src)

    def test_a_literal_credential_is_refused_and_an_env_reference_is_not(self):  # acceptance 3
        src = {"type": "sftp", "path": "sftp://h/in", "format": "csv"}
        for key in ("password", "sas_token", "client_secret"):
            msgs = [p for p in check_source_options({**src, "options": {key: "hunter2"}}) if key in p]
            self.assertEqual(len(msgs), 1)
            self.assertIn("connection secret", msgs[0])
        self.assertEqual(check_source_options({**src, "options": {"password": "env:SFTP_PASSWORD"}}), [])
        self.assertEqual(check_source_options({**src, "options": {"password": "${ENV:SFTP_PASSWORD}"}}), [])

    def test_fixed_width_keys_on_source_are_moved_by_the_message(self):  # acceptance 9
        [msg] = check_source_options({"type": "landing", "path": "x", "format": "fixed_width", "record_length": 80})
        self.assertEqual(msg, "source.record_length: `record_length` belongs under source.options")
        _valid({"type": "landing", "path": "x", "format": "fixed_width", "options": {"record_length": 80}})

    def test_an_unknown_format_is_refused_with_a_suggestion(self):
        [msg] = check_source_options({"type": "landing", "path": "x", "format": "cvs"})
        self.assertIn("did you mean 'csv'", msg)

    def test_values_are_checked_not_just_keys(self):
        [msg] = check_source_options(
            {"type": "stream", "options": {"kind": "kafka", "brokers": "b:9092", "trigger": "nightly"}}
        )
        self.assertIn("options.trigger", msg)
        [msg] = check_source_options({"type": "landing", "path": "x", "format": "xlsx", "options": {"header_row": 0}})
        self.assertIn("header_row", msg)

    def test_the_options_model_follows_type_format_and_kind(self):
        cases = [
            ({"type": "stream", "options": {"kind": "kafka"}}, "KafkaOptions"),
            ({"type": "stream", "options": {"kind": "eventhubs"}}, "EventHubsOptions"),
            ({"type": "database", "path": "mongodb+srv://c/db"}, "MongoDbOptions"),
            ({"type": "database", "path": "postgresql://h/db"}, "DatabaseOptions"),
            ({"type": "landing", "format": "csv"}, "CsvOptions"),
            ({"type": "landing", "format": "fixed_width"}, "FixedWidthOptions"),
        ]
        for source, model in cases:
            with self.subTest(model=model):
                self.assertEqual(options_models_for(source)[0].__name__, model)

    def test_an_env_database_path_accepts_sql_or_mongodb_keys(self):
        self.assertEqual(check_source_options({"type": "database", "path": "env:U", "options": {"fetch_size": 5}}), [])
        self.assertEqual(check_source_options({"type": "database", "path": "env:U", "options": {"database": "d"}}), [])

    def test_sftp_accepts_its_own_keys_and_the_formats(self):
        src = {"type": "sftp", "path": "sftp://h/in", "format": "csv",
               "options": {"username": "u", "known_hosts": "/k", "delimiter": ";"}}
        self.assertEqual(check_source_options(src), [])

    def test_the_example_contracts_shapes_are_valid(self):
        _valid({"type": "stream", "options": {"kind": "kafka", "brokers": "env:KAFKA_BROKERS", "topic": "rides",
                "starting_offsets": "earliest", "checkpoint": "data/c.sqlite", "batch_size": 100,
                "trigger": "available_now"}})
        _valid({"type": "stream", "options": {"kind": "eventhubs", "connection_string": "env:EH", "topic": "rides"}})
        _valid({"type": "database", "path": "env:AZURE_SQL_URI", "load_mode": "cdc",
                "options": {"cdc_provider": "azuresql", "cdc_capture_instance": "dbo_rides"}})
        _valid({"type": "database", "path": "env:MONGO_URI",
                "options": {"database": "d", "filter": {"status": {"$ne": "x"}}}})

    def test_every_option_and_format_is_described(self):  # spec part 3, for the options
        missing = [f"{m.__name__}.{n}" for model in OPTIONS_MODELS for m, n, f in _fields(model)
                   if not (f.description or "").strip()]
        self.assertEqual(missing, [])
        self.assertTrue(all(d.strip() for d in SOURCE_FORMAT_DESCRIPTIONS.values()))


if __name__ == "__main__":
    unittest.main()
