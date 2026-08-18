"""One-time adapter for the seven pre-existing Week-1 OCR probe artifacts.

This does not claim that OCR was rerun. It preserves the recognized text,
confidence, polygon, and duration while making the serialization conform to the
shared v1.3 schema. The original package version was not recorded, so provenance
is explicitly marked as unknown instead of being inferred from a model label.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from uuid import uuid5

from run_baseline import (
    BENCHMARK_NAMESPACE,
    OUTPUT_DIR,
    PROJECT_ROOT,
    build_ocr_result,
    load_validator,
    validate_ocr_result,
)

EVALUATED_TEST_IDS = ("R002", "R006", "R019", "R021", "R023", "R028")
MAPPING_PATH = PROJECT_ROOT / "results" / "legacy_artifact_mapping.csv"


def migrate(path: Path) -> tuple[dict, dict[str, str]]:
    with path.open(encoding="utf-8") as handle:
        legacy = json.load(handle)

    test_id = path.stem
    if legacy.get("schema_version") == "1.3":
        return legacy, {
            "test_id": test_id,
            "receipt_id": str(legacy["receipt_id"]),
            "ocr_run_id": str(legacy["ocr_run_id"]),
            "source_engine_label": "paddleocr_v4_unverified_legacy_label",
            "engine_package_version": "unknown",
            "provenance_status": "legacy_serialization_migrated_not_rerun",
        }

    receipt_id = uuid5(BENCHMARK_NAMESPACE, f"benchmark-receipt:{test_id}")
    original_run_label = str(legacy.get("ocr_run_id", "unrecorded"))
    ocr_run_id = uuid5(
        BENCHMARK_NAMESPACE, f"legacy-ocr-run:{test_id}:{original_run_label}"
    )
    blocks = legacy.get("blocks") or legacy.get("detections") or []
    raw_page = {
        "rec_texts": [block.get("text", "") for block in blocks],
        "rec_scores": [block.get("confidence", 0.0) for block in blocks],
        "rec_polys": [block.get("polygon", block.get("box", [])) for block in blocks],
    }
    image = legacy.get("image_size") or legacy.get("image") or {}
    width_px = int(image.get("width", image.get("width_px", 0)))
    height_px = int(image.get("height", image.get("height_px", 0)))

    document = build_ocr_result(
        raw_page,
        receipt_id=receipt_id,
        ocr_run_id=ocr_run_id,
        width_px=width_px,
        height_px=height_px,
        duration_ms=int(legacy.get("duration_ms", 0)),
    )
    document["engine"]["version"] = "legacy-unrecorded"
    return document, {
        "test_id": test_id,
        "receipt_id": str(receipt_id),
        "ocr_run_id": str(ocr_run_id),
        "source_engine_label": str(legacy.get("engine", "unrecorded")),
        "engine_package_version": "unknown",
        "provenance_status": "legacy_serialization_migrated_not_rerun",
    }


def main() -> None:
    validator = load_validator()
    mapping_rows: list[dict[str, str]] = []
    for test_id in EVALUATED_TEST_IDS:
        output_path = OUTPUT_DIR / f"{test_id}.json"
        document, mapping = migrate(output_path)
        validate_ocr_result(document, validator)
        with output_path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(document, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        mapping_rows.append(mapping)

    with MAPPING_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(mapping_rows[0]))
        writer.writeheader()
        writer.writerows(mapping_rows)

    print(f"Migrated and validated {len(mapping_rows)} legacy artifacts")


if __name__ == "__main__":
    main()
