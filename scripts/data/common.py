"""Portable bytes, canonical field names and manifest helpers."""

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HEADERS = (
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


def cell(value=None, status=None):
    return dict(
        annotation_status=status or ("PRESENT" if value is not None else "UNKNOWN"),
        raw_value=value,
        normalized_value=value,
        source_block_ids=[],
    )


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace("\r\n", "\n").encode("utf-8"))


def dump(path, data):
    write_text(
        path, json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):
    if not rows:
        raise ValueError("Cannot write an empty manifest")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def resolve(root, name):
    if not name or Path(name).is_absolute():
        raise ValueError("Expected nonempty relative artifact path")
    result = (Path(root) / name).resolve()
    if not result.is_relative_to(Path(root).resolve()):
        raise ValueError("Artifact path escapes dataset root")
    return result
