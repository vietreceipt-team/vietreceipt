from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


PROJECT_ROOT = Path(__file__).resolve().parents[2]

OCR_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "ocr-result.schema.json"
KIE_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "kie-result.schema.json"


def _load_validator(schema_path: Path) -> Draft202012Validator:
    with schema_path.open("r", encoding="utf-8") as handle:
        schema = json.load(handle)

    Draft202012Validator.check_schema(schema)

    return Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    )


_OCR_VALIDATOR = _load_validator(OCR_SCHEMA_PATH)
_KIE_VALIDATOR = _load_validator(KIE_SCHEMA_PATH)


def _validation_errors(
    validator: Draft202012Validator,
    document: dict[str, Any],
) -> list[str]:
    errors = sorted(
        validator.iter_errors(document),
        key=lambda error: [str(part) for part in error.absolute_path],
    )

    return [
        (
            f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: "
            f"{error.message}"
        )
        for error in errors
    ]


def validate_ocr_result(document: dict[str, Any]) -> None:
    errors = _validation_errors(_OCR_VALIDATOR, document)

    if errors:
        raise ValueError(
            "Invalid OCRResult v1.3:\n" + "\n".join(errors)
        )

    _validate_ocr_invariants(document)


def validate_kie_result(document: dict[str, Any]) -> None:
    errors = _validation_errors(_KIE_VALIDATOR, document)

    if errors:
        raise ValueError(
            "Invalid KIEResult v1.3:\n" + "\n".join(errors)
        )


def _validate_ocr_invariants(document: dict[str, Any]) -> None:
    blocks = document["blocks"]

    block_ids = [block["block_id"] for block in blocks]

    if len(block_ids) != len(set(block_ids)):
        raise ValueError(
            "Invalid OCRResult v1.3: block_id values must be unique"
        )

    reading_orders = [block["reading_order"] for block in blocks]

    expected = list(range(len(blocks)))

    if sorted(reading_orders) != expected:
        raise ValueError(
            "Invalid OCRResult v1.3: reading_order must be contiguous 0..N-1"
        )