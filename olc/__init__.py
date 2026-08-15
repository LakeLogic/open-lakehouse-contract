"""Open Lakehouse Contract — reference CLI and validator.

The specification is the JSON Schema in ``schema/``; this small package provides the
``olc`` command (validate + init) so contracts can be checked in CI and the agent
integrations installed. It depends only on ``jsonschema`` + ``pyyaml`` — never on a
lakehouse runtime.
"""

__all__ = ["validate", "init", "cli"]
