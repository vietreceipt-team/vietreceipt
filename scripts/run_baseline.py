"""Run the pinned PaddleOCR baseline and emit canonical OCRResult v1.3 JSON."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import os
import time
from collections.abc import Iterable, Sequence
from importlib.metadata import version
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4, uuid5

os.environ.setdefault("FLAGS_enable_pir_api", "0")
os.environ.setdefault(
    "PADDLE_PDX_CACHE_HOME",
    str(Path(__file__).resolve().parents[1] / ".paddlex-cache"),
)

from jsonschema import Draft202012Validator, FormatChecker
from PIL import Image, ImageOps

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_IMAGES_DIR = PROJECT_ROOT / "data" / "test_set" / "images"
OUTPUT_DIR = PROJECT_ROOT / "results" / "ocr_outputs"
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "ocr-result.schema.json"
MAPPING_PATH = PROJECT_ROOT / "results" / "benchmark_run_mapping.csv"

SCHEMA_VERSION = "1.3"
PADDLEOCR_PACKAGE_VERSION = "3.0.3"
PADDLEPADDLE_VERSION = "3.0.0"
PADDLEX_VERSION = "3.0.3"
OCR_MODEL_VERSION = "PP-OCRv3"
OCR_LANGUAGE = "vi"
BENCHMARK_NAMESPACE = UUID("47a9421b-df53-4c26-89e8-b3c23f93b820")


def verify_runtime_versions() -> None:
    expected = {
        "paddlepaddle": PADDLEPADDLE_VERSION,
        "paddleocr": PADDLEOCR_PACKAGE_VERSION,
        "paddlex": PADDLEX_VERSION,
    }
    mismatches = [
        f"{package}={version(package)} (expected {expected_version})"
        for package, expected_version in expected.items()
        if version(package) != expected_version
    ]
    if mismatches:
        raise RuntimeError("Unpinned OCR runtime: " + "; ".join(mismatches))


def _as_mapping(value: Any) -> dict[str, Any]:
    """Extract the serializable result mapping from a PaddleOCR result object."""
    if isinstance(value, dict):
        payload = value
    elif hasattr(value, "json"):
        payload = value.json
    else:
        try:
            payload = dict(value)
        except (TypeError, ValueError) as exc:
            raise TypeError("Unsupported PaddleOCR result type") from exc

    if isinstance(payload, dict) and isinstance(payload.get("res"), dict):
        return payload["res"]
    if not isinstance(payload, dict):
        raise TypeError("PaddleOCR result did not contain an object")
    return payload


def _canonical_polygon(
    polygon: Sequence[Sequence[float]], width_px: int, height_px: int
) -> list[dict[str, float]]:
    """Normalize four image points and order them TL, TR, BR, BL."""
    if len(polygon) != 4:
        raise ValueError(f"Expected a four-point polygon, got {len(polygon)} points")

    points: list[tuple[float, float]] = []
    for point in polygon:
        if len(point) != 2:
            raise ValueError("Each polygon point must contain x and y")
        x_px, y_px = float(point[0]), float(point[1])
        if not math.isfinite(x_px) or not math.isfinite(y_px):
            raise ValueError("Polygon coordinates must be finite")
        points.append((x_px, y_px))

    # In image coordinates (y grows downward), increasing atan2 gives clockwise
    # order. Rotate the cycle so its first point is the top-left corner.
    center_x = sum(point[0] for point in points) / 4
    center_y = sum(point[1] for point in points) / 4
    clockwise = sorted(
        points, key=lambda p: math.atan2(p[1] - center_y, p[0] - center_x)
    )
    top_left = min(points, key=lambda p: (p[0] + p[1], p[1], p[0]))
    start = clockwise.index(top_left)
    ordered = clockwise[start:] + clockwise[:start]
    return [
        {
            "x": round(min(1.0, max(0.0, x_px / width_px)), 6),
            "y": round(min(1.0, max(0.0, y_px / height_px)), 6),
        }
        for x_px, y_px in ordered
    ]


def build_ocr_result(
    raw_page: dict[str, Any],
    *,
    receipt_id: UUID,
    ocr_run_id: UUID,
    width_px: int,
    height_px: int,
    duration_ms: int,
) -> dict[str, Any]:
    """Adapt one PaddleOCR page result to the shared OCRResult v1.3 contract."""
    texts = list(raw_page.get("rec_texts") or [])
    scores = list(raw_page.get("rec_scores") or [])
    polygons = list(raw_page.get("rec_polys") or [])

    if len(scores) < len(texts) or len(polygons) < len(texts):
        raise ValueError(
            "PaddleOCR output is incomplete: every recognized text needs a score "
            "and a four-point polygon"
        )

    blocks: list[dict[str, Any]] = []
    for source_index, raw_text in enumerate(texts):
        text = str(raw_text).strip()
        if not text:
            continue

        confidence = float(scores[source_index])
        if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            raise ValueError(f"Invalid confidence for OCR block {source_index}")

        reading_order = len(blocks)
        blocks.append(
            {
                "block_id": f"block_{reading_order}",
                "text": text,
                "confidence": round(confidence, 6),
                "polygon": _canonical_polygon(
                    polygons[source_index], width_px, height_px
                ),
                "reading_order": reading_order,
            }
        )

    average_confidence = (
        round(sum(block["confidence"] for block in blocks) / len(blocks), 6)
        if blocks
        else 0.0
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "receipt_id": str(receipt_id),
        "ocr_run_id": str(ocr_run_id),
        "engine": {
            "name": "paddleocr",
            "version": PADDLEOCR_PACKAGE_VERSION,
        },
        "image": {"width_px": width_px, "height_px": height_px},
        "blocks": blocks,
        "average_confidence": average_confidence,
        "duration_ms": duration_ms,
    }


def load_validator(schema_path: Path = SCHEMA_PATH) -> Draft202012Validator:
    with schema_path.open(encoding="utf-8") as handle:
        schema = json.load(handle)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_ocr_result(
    document: dict[str, Any], validator: Draft202012Validator
) -> None:
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
    if errors:
        details = "; ".join(
            f"{'.'.join(map(str, error.path)) or '<root>'}: {error.message}"
            for error in errors
        )
        raise ValueError(f"OCRResult v1.3 validation failed: {details}")


def process_image(
    ocr_engine: Any,
    image_path: Path,
    *,
    receipt_id: UUID,
    ocr_run_id: UUID,
) -> dict[str, Any]:
    """Run OCR after EXIF orientation and return a validated adapter document."""
    import numpy as np

    start_time = time.perf_counter()
    with Image.open(image_path) as image:
        oriented_image = ImageOps.exif_transpose(image).convert("RGB")
        width_px, height_px = oriented_image.size
        result_pages = list(ocr_engine.predict(np.asarray(oriented_image)))

    duration_ms = int((time.perf_counter() - start_time) * 1000)
    raw_page = _as_mapping(result_pages[0]) if result_pages else {}
    return build_ocr_result(
        raw_page,
        receipt_id=receipt_id,
        ocr_run_id=ocr_run_id,
        width_px=width_px,
        height_px=height_px,
        duration_ms=duration_ms,
    )


def _image_paths(selected_image: Path | None) -> list[Path]:
    if selected_image is not None:
        image_path = selected_image.resolve()
        if not image_path.is_file():
            raise FileNotFoundError(f"Image not found: {image_path}")
        return [image_path]

    valid_extensions = {".jpg", ".jpeg", ".png"}
    return sorted(
        path
        for path in TEST_IMAGES_DIR.glob("*.*")
        if path.suffix.lower() in valid_extensions
    )


def _write_mapping(rows: Iterable[dict[str, str]], mapping_path: Path) -> None:
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    with mapping_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["test_id", "receipt_id", "ocr_run_id", "output_file"],
        )
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--image",
        type=Path,
        help="Run one image. Without this option, run the local frozen test images.",
    )
    parser.add_argument(
        "--receipt-id",
        type=UUID,
        help="Backend-supplied receipt UUID (single-image integration mode only).",
    )
    parser.add_argument(
        "--ocr-run-id",
        type=UUID,
        help="Backend-supplied OCR run UUID (single-image integration mode only).",
    )
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--mapping-out", type=Path, default=MAPPING_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    image_paths = _image_paths(args.image)
    if not image_paths:
        raise SystemExit(
            "No local test images found. See data/test_set/README.md for the "
            "authorized acquisition procedure."
        )
    if bool(args.receipt_id) != bool(args.ocr_run_id):
        raise SystemExit("--receipt-id and --ocr-run-id must be supplied together")
    if args.receipt_id and len(image_paths) != 1:
        raise SystemExit("Backend UUIDs can only be used with --image")

    from paddleocr import PaddleOCR

    verify_runtime_versions()
    logger.info(
        "Initializing PaddleOCR package %s with model=%s, lang=%s",
        PADDLEOCR_PACKAGE_VERSION,
        OCR_MODEL_VERSION,
        OCR_LANGUAGE,
    )
    ocr_engine = PaddleOCR(
        lang=OCR_LANGUAGE,
        ocr_version=OCR_MODEL_VERSION,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=True,
        enable_mkldnn=False,
    )
    validator = load_validator()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    mapping_rows: list[dict[str, str]] = []
    for image_path in image_paths:
        test_id = image_path.stem
        receipt_id = args.receipt_id or uuid5(
            BENCHMARK_NAMESPACE, f"benchmark-receipt:{test_id}"
        )
        ocr_run_id = args.ocr_run_id or uuid4()
        logger.info("Processing %s", image_path.name)
        document = process_image(
            ocr_engine,
            image_path,
            receipt_id=receipt_id,
            ocr_run_id=ocr_run_id,
        )
        validate_ocr_result(document, validator)

        output_file = output_dir / f"{test_id}.json"
        with output_file.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(document, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        mapping_rows.append(
            {
                "test_id": test_id,
                "receipt_id": str(receipt_id),
                "ocr_run_id": str(ocr_run_id),
                "output_file": output_file.relative_to(PROJECT_ROOT).as_posix(),
            }
        )

    _write_mapping(mapping_rows, args.mapping_out.resolve())
    logger.info("Validated %d OCRResult v1.3 artifact(s)", len(mapping_rows))


if __name__ == "__main__":
    main()
