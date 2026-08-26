"""Canonical OCRResult v1.3 validation, including cross-field invariants."""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "ocr-result.schema.json"


def load_ocr_validator(
    schema_path: Path = SCHEMA_PATH,
) -> Draft202012Validator:
    """Load and check the one canonical OCRResult schema."""
    with schema_path.open(encoding="utf-8") as handle:
        schema = json.load(handle)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def order_polygon_points(
    polygon: Sequence[Sequence[float]],
) -> list[tuple[float, float]]:
    """Return four image-space points in TL, TR, BR, BL order."""
    if len(polygon) != 4:
        raise ValueError(f"Expected a four-point polygon, got {len(polygon)} points")

    points: list[tuple[float, float]] = []
    for point in polygon:
        if len(point) != 2:
            raise ValueError("Each polygon point must contain x and y")
        x, y = float(point[0]), float(point[1])
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("Polygon coordinates must be finite")
        points.append((x, y))

    if len(set(points)) != 4:
        raise ValueError("Polygon points must be unique")

    center_x = sum(point[0] for point in points) / 4
    center_y = sum(point[1] for point in points) / 4
    clockwise = sorted(
        points, key=lambda point: math.atan2(point[1] - center_y, point[0] - center_x)
    )
    top_left = min(points, key=lambda point: (point[0] + point[1], point[1], point[0]))
    start = clockwise.index(top_left)
    return clockwise[start:] + clockwise[:start]


def _validate_invariants(document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    blocks = document.get("blocks")
    if not isinstance(blocks, list):
        return errors
    image = document.get("image") if isinstance(document.get("image"), dict) else {}
    width_px = image.get("width_px", 1)
    height_px = image.get("height_px", 1)

    block_ids = [block.get("block_id") for block in blocks if isinstance(block, dict)]
    if len(block_ids) == len(blocks) and len(block_ids) != len(set(block_ids)):
        errors.append("blocks: block_id values must be unique within an OCR run")

    reading_order = [
        block.get("reading_order") for block in blocks if isinstance(block, dict)
    ]
    if len(reading_order) == len(blocks) and reading_order != list(range(len(blocks))):
        errors.append("blocks: reading_order must be contiguous and zero-based")

    for index, block in enumerate(blocks):
        if not isinstance(block, dict):
            continue
        polygon = block.get("polygon")
        if not isinstance(polygon, list) or len(polygon) != 4:
            continue
        try:
            supplied = [(float(point["x"]), float(point["y"])) for point in polygon]
            # Point ordering is defined in image coordinates. Reinflate normalized
            # coordinates before determining the top-left point so aspect ratio does
            # not change the ordering decision made by the adapter.
            supplied_image_space = [
                (x * float(width_px), y * float(height_px)) for x, y in supplied
            ]
            order_polygon_points(supplied_image_space)
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"blocks.{index}.polygon: {exc}")
            continue
        signed_area_twice = sum(
            supplied_image_space[point_index][0]
            * supplied_image_space[(point_index + 1) % 4][1]
            - supplied_image_space[(point_index + 1) % 4][0]
            * supplied_image_space[point_index][1]
            for point_index in range(4)
        )
        corner_sums = [x + y for x, y in supplied_image_space]
        # Quantization to six normalized decimals can move the winner of an
        # almost-tied x+y comparison for tiny, rotated boxes. Two image pixels
        # preserve the adapter's TL choice without accepting another corner.
        starts_at_top_left = corner_sums[0] <= min(corner_sums) + 2.0
        if signed_area_twice <= 0 or not starts_at_top_left:
            errors.append(
                f"blocks.{index}.polygon: points must be ordered TL, TR, BR, BL"
            )
    return errors


def validate_ocr_result(
    document: dict[str, Any],
    validator: Draft202012Validator | None = None,
) -> None:
    """Fail before integration/persistence when schema or invariants are invalid."""
    active_validator = validator or load_ocr_validator()
    schema_errors = sorted(
        active_validator.iter_errors(document), key=lambda error: list(error.path)
    )
    details = [
        f"{'.'.join(map(str, error.path)) or '<root>'}: {error.message}"
        for error in schema_errors
    ]
    details.extend(_validate_invariants(document))
    if details:
        raise ValueError("OCRResult v1.3 validation failed: " + "; ".join(details))
