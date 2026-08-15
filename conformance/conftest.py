"""Conformance pytest config.

In strict/CI mode (``OLC_CONFORMANCE_REQUIRE=1``) a skipped test is treated as a
failure: the whole point of the CI job is to actually exercise the runtime, so any
skip — a missing dependency, a ``pytest.skip`` in a future case, an empty
parametrization — must turn CI red rather than pass silently.
"""

from __future__ import annotations

import os

REQUIRE = os.environ.get("OLC_CONFORMANCE_REQUIRE") == "1"


def pytest_sessionfinish(session, exitstatus):
    """Force a non-zero exit if anything was skipped while running in strict mode."""
    if not REQUIRE:
        return
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    skipped = reporter.stats.get("skipped", []) if reporter else []
    if skipped:
        names = "\n  ".join(rep.nodeid for rep in skipped)
        reporter.write_line(
            f"ERROR: OLC_CONFORMANCE_REQUIRE=1 but {len(skipped)} test(s) were skipped:\n  {names}",
            red=True,
        )
        # Setting session.exitstatus here propagates to the process exit code.
        session.exitstatus = 1
