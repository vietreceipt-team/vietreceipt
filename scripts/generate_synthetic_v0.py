"""Compatibility entry point for corrected synthetic generator v0.2.0."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.data.generate_synthetic import main

if __name__ == "__main__":
    main()
