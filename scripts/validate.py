"""Validate Open Lakehouse Contract files against the JSON Schema — zero-install entry point.

Works from a checkout with only ``jsonschema`` + ``pyyaml`` installed (no need to install
the ``olc`` package), so it's ideal for CI. It simply delegates to ``olc.validate``.

    pip install jsonschema pyyaml
    python scripts/validate.py                     # discover **/*.olc.yaml
    python scripts/validate.py contracts/*.olc.yaml --schema https://…/schema.json
"""

import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1])
)  # repo root → import olc without installing
from olc.validate import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
