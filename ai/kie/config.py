from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


CONFIG_PATH = (
    Path(__file__).resolve().parent
    / "resources"
    / "baseline-config-v0.1.yaml"
)


def load_baseline_config() -> dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    if not isinstance(config, dict):
        raise ValueError("Baseline config must be a YAML mapping")

    if config.get("version") != "baseline-ranking-v0.1":
        raise ValueError(
            "Unsupported baseline config version: "
            f"{config.get('version')!r}"
        )

    weights = config.get("weights")

    if not isinstance(weights, dict):
        raise ValueError("Baseline config is missing weights")

    required_weights = {
        "pattern",
        "context",
        "layout",
        "ocr_quality",
    }

    if set(weights) != required_weights:
        raise ValueError(
            "Baseline config weights must contain exactly: "
            + ", ".join(sorted(required_weights))
        )

    weight_sum = sum(float(value) for value in weights.values())

    if abs(weight_sum - 1.0) > 1e-9:
        raise ValueError(
            f"Baseline ranking weights must sum to 1.0, got {weight_sum}"
        )

    return config