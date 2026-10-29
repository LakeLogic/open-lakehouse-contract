"""The contract's ``profiling`` block (lakelogic profile --contract).

unittest, not pytest: ``tests/`` runs under ``python -m unittest discover``.
"""
import unittest

from pydantic import ValidationError

from olc.models._nested import Profiling
from olc.models.olc_v1 import OLCContractV1

BASE = {"version": "1.0.0", "info": {"title": "Trips"}, "model": {"fields": [{"name": "id", "type": "integer"}]}}


class ProfilingBlockTests(unittest.TestCase):
    def test_a_contract_may_say_how_to_profile_it(self):
        c = OLCContractV1.model_validate({**BASE, "profiling": {"mode": "sample", "sample_rows": 5000}})
        self.assertTrue(c.profiling.mode == "sample" and c.profiling.sample_rows == 5000 and c.profiling.findings)

    def test_defaults_profile_everything_with_findings(self):
        p = Profiling()
        self.assertEqual((p.enabled, p.mode, p.findings), (True, "full", True))

    def test_an_invalid_profiling_block_is_refused(self):
        for bad in (
            {"mode": "sample"},                                            # no size
            {"mode": "sample", "sample_rows": 5000, "sample_percent": 5},  # both sizes
            {"sample_rows": 10},                                           # below the floor
            {"unknown": 1},
        ):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                Profiling.model_validate(bad)


if __name__ == "__main__":
    unittest.main()
