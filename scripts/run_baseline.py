"""Run the pinned PaddleOCR baseline and emit immutable OCRResult v1.3 JSON."""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from collections.abc import Iterable
from pathlib import Path
from uuid import UUID, uuid4, uuid5

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai.ocr.artifacts import ImmutableOCRArtifactStore
from ai.ocr.contract import load_ocr_validator, validate_ocr_result
from ai.ocr.pipeline import (
    OCRPipeline,
    OCR_LANGUAGE,
    OCR_MODEL_VERSION,
    PADDLEOCR_PACKAGE_VERSION,
    PADDLEPADDLE_VERSION,
    PADDLEX_VERSION,
    SCHEMA_VERSION,
    build_ocr_result,
    create_paddleocr_engine,
    verify_runtime_versions,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

TEST_IMAGES_DIR = PROJECT_ROOT / "data" / "test_set" / "images"
OUTPUT_DIR = PROJECT_ROOT / "results" / "ocr_outputs"
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "ocr-result.schema.json"
MAPPING_PATH = PROJECT_ROOT / "results" / "benchmark_run_mapping.csv"
BENCHMARK_NAMESPACE = UUID("47a9421b-df53-4c26-89e8-b3c23f93b820")

# Backwards-compatible name used by the Week-1 regression suite.
load_validator = load_ocr_validator


def process_image(
    ocr_engine: object,
    image_path: Path,
    *,
    receipt_id: UUID,
    ocr_run_id: UUID,
) -> dict[str, object]:
    """Compatibility wrapper around the integration-ready validated pipeline."""
    return OCRPipeline(ocr_engine).run_ocr(
        image_path, receipt_id=receipt_id, ocr_run_id=ocr_run_id
    )


def _image_paths(selected_image: Path | None) -> list[Path]:
    if selected_image is not None:
        image_path = selected_image.resolve()
        if not image_path.is_file():
            raise FileNotFoundError(f"Image not found: {image_path}")
        return [image_path]

    valid_extensions = {".jpg", ".jpeg", ".png", ".webp"}
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


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


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
        help="Orchestration-supplied OCR run UUID (single-image mode only).",
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

    logger.info(
        "Initializing PaddleOCR package %s with model=%s, lang=%s",
        PADDLEOCR_PACKAGE_VERSION,
        OCR_MODEL_VERSION,
        OCR_LANGUAGE,
    )
    pipeline = OCRPipeline(create_paddleocr_engine())
    artifact_store = ImmutableOCRArtifactStore(args.output_dir)

    mapping_rows: list[dict[str, str]] = []
    for image_path in image_paths:
        test_id = image_path.stem
        receipt_id = args.receipt_id or uuid5(
            BENCHMARK_NAMESPACE, f"benchmark-receipt:{test_id}"
        )
        ocr_run_id = args.ocr_run_id or uuid4()
        logger.info("Processing %s", image_path.name)
        document = pipeline.run_ocr(
            image_path, receipt_id=receipt_id, ocr_run_id=ocr_run_id
        )
        output_file = artifact_store.write(document)
        mapping_rows.append(
            {
                "test_id": test_id,
                "receipt_id": str(receipt_id),
                "ocr_run_id": str(ocr_run_id),
                "output_file": _display_path(output_file),
            }
        )

    _write_mapping(mapping_rows, args.mapping_out.resolve())
    logger.info("Validated and stored %d immutable OCRResult artifact(s)", len(mapping_rows))


if __name__ == "__main__":
    main()
