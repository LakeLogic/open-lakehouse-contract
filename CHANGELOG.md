# Changelog

## v1 (draft)
- Initial Open Lakehouse Contract spec: JSON Schema (Draft 2020-12) generated from the
  reference implementation (LakeLogic `DataContract`).
- Conformance suite (valid + invalid fixtures) validated against the schema.
- Example contract (`examples/orders.olc.yaml`).
- ODCS interoperability documented (reference runtime imports/exports ODCS).
- Strict typed objects reject unknown keys, while namespaced `extensions` provide an
  explicit vendor escape hatch.
- `version`, `info`, and `model` now form the required minimum contract; versions use
  semantic-version form.
- CLI validation now supports recursive roots, machine-readable JSON, duplicate-key
  detection, bounded HTTPS schema loading, and explicit empty-directory handling.
- `olc init` now preflights every destination, preserves identical files, refuses
  conflicts by default, and supports `--dry-run` and explicit `--force` replacement.
- Added 25 unit/CLI tests, recursive conformance coverage, a Python-version CI matrix,
  and pull-request wheel smoke testing.
