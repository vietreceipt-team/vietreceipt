from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _validator(name: str) -> Draft202012Validator:
    with (PROJECT_ROOT / "schemas" / name).open(encoding="utf-8") as handle:
        schema = json.load(handle)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


OCR_VALIDATOR = _validator("ocr-result.schema.json")
KIE_VALIDATOR = _validator("kie-result.schema.json")


def is_schema_valid(payload: Any, *, kind: str) -> bool:
    if not isinstance(payload, dict):
        return False
    validator = OCR_VALIDATOR if kind == "ocr" else KIE_VALIDATOR
    return not any(validator.iter_errors(payload))
