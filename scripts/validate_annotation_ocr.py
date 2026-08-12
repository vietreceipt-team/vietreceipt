#!/usr/bin/env python3
"""Validate cross-record linkage between one annotation and one OCR result."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def linkage_errors(annotation: dict[str, Any], ocr_result: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if annotation.get("receipt_id") != ocr_result.get("receipt_id"):
        errors.append("annotation.receipt_id does not match ocr.receipt_id")

    if annotation.get("source_ocr_run_id") != ocr_result.get("ocr_run_id"):
        errors.append("annotation.source_ocr_run_id does not match ocr.ocr_run_id")

    block_ids = [block.get("block_id") for block in ocr_result.get("blocks", [])]
    if len(block_ids) != len(set(block_ids)):
        errors.append("ocr.blocks contains duplicate block_id values")

    known_block_ids = set(block_ids)
    for field_key, field in annotation.get("fields", {}).items():
        for block_id in field.get("source_block_ids", []):
            if block_id not in known_block_ids:
                errors.append(
                    f"annotation.fields.{field_key}.source_block_ids contains "
                    f"unknown block_id {block_id!r}"
                )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotation", required=True, type=Path)
    parser.add_argument("--ocr", required=True, type=Path)
    args = parser.parse_args()

    try:
        annotation = load_json(args.annotation)
        ocr_result = load_json(args.ocr)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Unable to read input: {exc}", file=sys.stderr)
        return 2

    errors = linkage_errors(annotation, ocr_result)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("Cross-record annotation/OCR linkage: valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
