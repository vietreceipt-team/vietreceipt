import json
import math
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from .errors import V2Error

ROOT = Path(__file__).resolve().parents[3]
HEADER_FIELDS = (
    "invoice_template_number",
    "invoice_symbol",
    "invoice_number",
    "invoice_date",
    "seller_name",
    "seller_tax_id",
    "seller_address",
    "buyer_name",
    "buyer_tax_id",
    "subtotal",
    "tax_amount",
    "total_amount",
    "currency",
)
LINE_FIELDS = ("description", "unit", "quantity", "unit_price", "amount")
TAX_FIELDS = ("rate", "taxable_amount", "tax_amount")
STATUSES = ("PRESENT", "NOT_PRESENT", "UNREADABLE", "AMBIGUOUS", "UNKNOWN")


@lru_cache
def validator(name):
    return Draft202012Validator(
        json.loads((ROOT / "schemas" / name).read_text()),
        format_checker=FormatChecker(),
    )


def invalid():
    return V2Error(
        "SCHEMA_VALIDATION_FAILED",
        "Provider output does not satisfy the invoice contract.",
        422,
        False,
    )


def xml_text_ok(text):
    return all(
        ord(char) in (9, 10, 13)
        or 0x20 <= ord(char) <= 0xD7FF
        or 0xE000 <= ord(char) <= 0xFFFD
        or 0x10000 <= ord(char) <= 0x10FFFF
        for char in text
    )


def validate_transport(payload):
    # PostgreSQL JSON, strict API JSON and XLSX must all accept the provider output.
    try:
        json.dumps(payload, allow_nan=False)

        def strings(obj):
            if isinstance(obj, str):
                if not xml_text_ok(obj):
                    raise invalid()
            elif isinstance(obj, dict):
                for key, value in obj.items():
                    strings(key)
                    strings(value)
            elif isinstance(obj, (list, tuple)):
                for value in obj:
                    strings(value)

        strings(payload)
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        raise invalid() from exc


def validate_evidence(evidence, receipt_id, ocr_run_id):
    try:
        validate_transport(evidence)
        if evidence.get("schema_version") == "document-2.0":
            if (
                set(evidence) != {"schema_version", "receipt_id", "ocr_run_id", "pages"}
                or not evidence["pages"]
            ):
                raise invalid()
            pages = evidence["pages"]
            for index, page in enumerate(pages):
                if (
                    set(page) != {"page_index", "evidence"}
                    or page["page_index"] != index
                ):
                    raise invalid()
                validate_evidence(page["evidence"], receipt_id, ocr_run_id)
            ids = [b["block_id"] for p in pages for b in p["evidence"]["blocks"]]
            if len(ids) != len(set(ids)):
                raise invalid()
        else:
            validator("ocr-result.schema.json").validate(evidence)
            ids = [b["block_id"] for b in evidence["blocks"]]
            orders = [b["reading_order"] for b in evidence["blocks"]]
            if len(ids) != len(set(ids)) or len(orders) != len(set(orders)):
                raise invalid()
        if evidence["receipt_id"] != receipt_id or evidence["ocr_run_id"] != ocr_run_id:
            raise invalid()
    except (ValidationError, KeyError, TypeError, AttributeError, ValueError) as exc:
        raise invalid() from exc


def evidence_ids(evidence):
    if evidence.get("schema_version") == "document-2.0":
        return {
            b["block_id"] for p in evidence["pages"] for b in p["evidence"]["blocks"]
        }
    return {b["block_id"] for b in evidence["blocks"]}


def cells(result):
    for field, val in result["fields"].items():
        yield "header", "", 0, field, val
    for index, row in enumerate(result["line_items"]):
        for field in LINE_FIELDS:
            yield "line", row["line_id"], index, field, row[field]
    for index, row in enumerate(result["tax_breakdown"]):
        for field in TAX_FIELDS:
            yield "tax", str(index), index, field, row[field]


def validate_result(result, evidence, receipt_id, kie_run_id, ocr_run_id):
    try:
        validate_transport(result)
        validator("invoice-kie-result.v2.schema.json").validate(result)
        if (
            result["receipt_id"],
            result["kie_run_id"],
            result["source_ocr_run_id"],
        ) != (receipt_id, kie_run_id, ocr_run_id):
            raise invalid()
        line_ids = [x["line_id"] for x in result["line_items"]]
        if len(line_ids) != len(set(line_ids)) or any(len(x) > 128 for x in line_ids):
            raise invalid()
        ids = evidence_ids(evidence)
        for section, row, index, field, val in cells(result):
            validate_value(section, field, val["normalized_value"], val["value_status"])
            if not set(val["source_block_ids"]) <= ids:
                raise invalid()
            if val["value_status"] == "PRESENT" and not val["source_block_ids"]:
                raise invalid()
    except (
        ValidationError,
        KeyError,
        TypeError,
        AttributeError,
        ValueError,
        V2Error,
    ) as exc:
        raise invalid() from exc


def validate_value(section, field, value, status):
    from datetime import date

    allowed = {"header": HEADER_FIELDS, "line": LINE_FIELDS, "tax": TAX_FIELDS}
    if (
        section not in allowed
        or field not in allowed[section]
        or status not in STATUSES
    ):
        raise V2Error("INVALID_VALUE", "Unknown field or value status.")
    if status != "PRESENT":
        if value is not None:
            raise V2Error("INVALID_VALUE", "Non-present values must be null.")
        return
    money = field in (
        "subtotal",
        "tax_amount",
        "total_amount",
        "unit_price",
        "amount",
        "taxable_amount",
    )
    if money:
        valid = type(value) is int and value >= 0
    elif field == "quantity":
        valid = type(value) in (int, float) and math.isfinite(value) and value >= 0
    else:
        valid = (
            isinstance(value, str)
            and bool(value.strip())
            and len(value) <= 10000
            and xml_text_ok(value)
        )
        if valid and field == "invoice_date":
            try:
                valid = date.fromisoformat(value).isoformat() == value
            except ValueError:
                valid = False
    if not valid:
        raise V2Error("INVALID_VALUE", "Value does not match the field type.")
