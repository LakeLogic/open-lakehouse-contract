"""Wherever data can be written, its rejects and run log can be written too (2026-11-18).

The runtime writes quarantine (``format: dlt``) and the run log (``run_log_backend: dlt``) to a
database such as Postgres, but the schema closed those objects, so an editor's IntelliSense
flagged the keys that say which database.
"""
import json
from pathlib import Path

import jsonschema

from olc.models._nested import Quarantine
from olc.models.registry_v1 import SystemMetadata

SCHEMA = json.loads((Path(__file__).parents[1] / "schema" / "open-lakehouse-contract.schema.json").read_text())


def test_quarantine_to_postgres_is_valid_in_the_published_schema():
    q = {"format": "dlt", "table": "quarantine_orders", "dlt_destination": "postgres",
         "dlt_credentials": "env:PG_URL", "dlt_dataset_name": "quarantine"}
    sub = {"$defs": SCHEMA["$defs"], **SCHEMA["$defs"]["Quarantine"]}
    jsonschema.validate(q, sub)
    assert Quarantine(**q).dlt_destination == "postgres"


def test_run_log_to_postgres_is_declared():
    m = SystemMetadata(run_log_backend="dlt", run_log_table="run_logs",
                       dlt_destination="postgres", dlt_credentials="env:PG_URL")
    assert m.dlt_destination == "postgres" and m.run_log_backend == "dlt"


def test_on_dataset_failure_policy_and_the_old_flag():
    import pytest
    from olc.models._nested import Quality

    assert Quality().dataset_failure_policy == "continue"
    assert Quality(fail_pipeline_on_dataset_error=True).dataset_failure_policy == "stop"
    assert Quality(on_dataset_failure="quarantine").dataset_failure_policy == "quarantine"
    with pytest.raises(ValueError):
        Quality(fail_pipeline_on_dataset_error=True, on_dataset_failure="quarantine")
    sub = {"$defs": SCHEMA["$defs"], **SCHEMA["$defs"]["Quality"]}
    jsonschema.validate({"on_dataset_failure": "quarantine"}, sub)
