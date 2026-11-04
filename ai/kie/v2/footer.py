"""Extract printed invoice totals from one explicit Layout region."""

import re

from .cells import Candidate, add_reason, select
from .config import ROW_OVERLAP, TOLERANCE_VND
from .evidence import flatten, same_row
from .extraction import LABELS, label_match, visual_rows
from .normalization import text

FOOTER_LABELS = {
    "subtotal": rf"tong (?:cong )?tien hang(?: hoa)?|{LABELS['subtotal']}",
    "tax_amount": rf"(?:tong )?tien thue vat|{LABELS['tax_amount']}|vat",
    "total_amount": rf"tong (?:tien )?phai thanh toan|{LABELS['total_amount']}",
}
RATE = re.compile(r"^(?:\(\s*\d+(?:[.,]\d+)?\s*%\s*\)|\d+(?:[.,]\d+)?\s*%)")
CURRENCY_MARKER = r"VND|VNĐ|đ|₫|USD|EUR|GBP|JPY|CNY|\$|€|¥"
AMOUNT_LIKE = re.compile(
    rf"(?:(?:{CURRENCY_MARKER})\s*)?-?[\d?\ufffd][\d .,?\ufffd]*(?:\s*(?:{CURRENCY_MARKER}))?",
    re.IGNORECASE,
)


def _region_blocks(evidence, region):
    if not isinstance(region, dict):
        raise ValueError("Footer region must be an object with page and bbox")
    page, bbox = region.get("page"), region.get("bbox")
    if type(page) is not int or page < 0:
        raise ValueError("Footer page must be a nonnegative integer")
    if (
        not isinstance(bbox, (list, tuple))
        or len(bbox) != 4
        or any(type(v) not in (int, float) or not 0 <= v <= 1 for v in bbox)
    ):
        raise ValueError("Footer bbox must contain four normalized coordinates")
    left, top, right, bottom = bbox
    if not (left < right and top < bottom):
        raise ValueError("Footer bbox must have positive area")

    blocks = flatten(evidence)
    page_count = (
        len(evidence["pages"]) if evidence["schema_version"] == "document-2.0" else 1
    )
    if page >= page_count:
        raise ValueError("Footer page is outside the evidence document")

    selected = []
    for block in blocks:
        if (
            block.page != page
            or block.right <= left
            or right <= block.left
            or block.bottom <= top
            or bottom <= block.top
        ):
            continue
        if not (
            left <= block.left
            and block.right <= right
            and top <= block.top
            and block.bottom <= bottom
        ):
            raise ValueError(f"Footer boundary crosses source block: {block.block_id}")
        selected.append(block)
    return selected


def _amount_text(value, field):
    value = value.lstrip(" :#：")
    if field == "tax_amount":
        value = RATE.sub("", value, count=1).lstrip(" :#：")
    return value


def extract_footer(
    evidence: dict, region: dict, *, currency: str | None = "VND"
) -> dict:
    """Return KIE V2 field cells for one zero-based page and normalized bbox."""
    candidates = {field: [] for field in FOOTER_LABELS}
    labels = {field: [] for field in FOOTER_LABELS}

    for row in visual_rows(_region_blocks(evidence, region)):
        anchor = None
        for block in row:
            match = label_match(block.text, FOOTER_LABELS)
            if match:
                field, inline = match
                value = _amount_text(inline, field)
                anchor = None
                if not value or AMOUNT_LIKE.fullmatch(value):
                    labels[field].append(block)
                    if value:
                        candidates[field].append(Candidate(value, (block,)))
                    else:
                        anchor = (field, block)
                continue

            if anchor is None:
                continue
            field, label = anchor
            if block.left < label.right or not same_row(label, block, ROW_OVERLAP):
                anchor = None
                continue
            raw = text(block.text)
            value = _amount_text(raw, field)
            if not value:
                continue  # A separator or a printed tax rate between label and amount.
            if AMOUNT_LIKE.fullmatch(value):
                candidates[field].append(Candidate(value, (label, block)))
            else:
                anchor = None

    fields = {}
    for field, options in candidates.items():
        cell = select(field, options, currency=currency)
        if not options and labels[field]:
            source = sorted(labels[field], key=lambda block: block.reading_order)
            cell["source_block_ids"] = [block.block_id for block in source]
            cell["raw_text"] = "\n".join(block.text for block in source)
        fields[field] = cell

    subtotal, tax, total = (cell["normalized_value"] for cell in fields.values())
    if (
        currency == "VND"
        and subtotal is not None
        and tax is not None
        and total is not None
        and abs(subtotal + tax - total) > TOLERANCE_VND
    ):
        for cell in fields.values():
            add_reason(cell, "CONSISTENCY_WARNING")
    return fields
