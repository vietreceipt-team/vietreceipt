"""Canonical schema and cross-record evidence invariants."""

import json
from functools import lru_cache
from pathlib import Path
from uuid import UUID

from jsonschema import Draft202012Validator, FormatChecker

from .config import LINE_FIELDS, TAX_FIELDS
from .evidence import flatten


@lru_cache
def validator():
    schema = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "schemas/invoice-kie-result.v2.schema.json"
        ).read_text()
    )
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def cells(result):
    yield from result["fields"].values()
    for row in result["line_items"]:
        yield from (row[field] for field in LINE_FIELDS)
    for group in result["tax_breakdown"]:
        yield from (group[field] for field in TAX_FIELDS)


def validate_result(result: dict, evidence: dict, *, kie_run_id: UUID):
    json.dumps(result, allow_nan=False)
    validator().validate(result)
    blocks = flatten(evidence)
    by_id = {b.block_id: b for b in blocks}
    if (result["receipt_id"], result["source_ocr_run_id"], result["kie_run_id"]) != (
        evidence["receipt_id"],
        evidence["ocr_run_id"],
        str(kie_run_id),
    ):
        raise ValueError("KIE receipt/run identity mismatch")
    for cell in cells(result):
        ids = cell["source_block_ids"]
        if not set(ids) <= by_id.keys():
            raise ValueError("Unknown source block ID")
        source = sorted(
            (by_id[i] for i in ids), key=lambda b: (b.page, b.reading_order)
        )
        if ids != [b.block_id for b in source]:
            raise ValueError("Source IDs must follow page/reading order")
        expected = "\n".join(b.text for b in source) if source else None
        if cell["raw_text"] != expected:
            raise ValueError("raw_text differs from immutable source evidence")
    ids = [row["line_id"] for row in result["line_items"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate line_id")
    for row in result["line_items"]:
        sources = {i for field in LINE_FIELDS for i in row[field]["source_block_ids"]}
        reasons = {r for field in LINE_FIELDS for r in row[field]["review_reasons"]}
        if (
            set(row["source_block_ids"]) != sources
            or set(row["review_reasons"]) != reasons
            or row["machine_needs_review"]
            != any(row[f]["machine_needs_review"] for f in LINE_FIELDS)
        ):
            raise ValueError("Row metadata must aggregate its cells")
