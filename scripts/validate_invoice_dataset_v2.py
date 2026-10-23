"""Compatibility entry point for independent source-gold QA."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.data.validate_ground_truth import FIELDS as FIELDS, audit as audit, main

if __name__ == "__main__":
    raise SystemExit(main())
