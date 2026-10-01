"""Label candidates and page-local table reconstruction, without absolute positions."""

import re

from .cells import Candidate, add_reason, select
from .config import (
    CONTINUATION_HEIGHTS,
    HEADER_FIELDS,
    LINE_FIELDS,
    REVIEW_VERSION,
    ROW_OVERLAP,
)
from .evidence import same_row
from .normalization import folded, text

LABELS = {
    "invoice_template_number": r"mau so|invoice template(?: number)?",
    "invoice_symbol": r"ky hieu|invoice symbol|serial",
    "invoice_number": r"so hoa don|invoice (?:number|no\.?)|so(?:\s*\(no\.?\))?",
    "invoice_date": r"ngay lap(?: hoa don)?|ngay hoa don|invoice date|date|ngay",
    "seller_name": r"(?:ten )?(?:don vi ban hang|nguoi ban|ben ban)|seller(?: name)?",
    "buyer_name": r"(?:ho ten )?nguoi mua(?: hang)?|(?:ten )?(?:don vi mua hang|ben mua)|buyer(?: name)?|khach hang",
    "seller_tax_id": r"(?:ma so thue|mst)(?: nguoi ban| ben ban)|seller tax (?:id|code)",
    "buyer_tax_id": r"(?:ma so thue|mst)(?: nguoi mua| ben mua)|buyer tax (?:id|code)",
    "seller_address": r"dia chi (?:nguoi ban|ben ban)|seller address",
    "subtotal": r"cong tien hang|tong (?:tien )?truoc thue|tam tinh|subtotal|sub total",
    "tax_amount": r"tong tien thue(?: gtgt)?|tien thue(?: gtgt)?|tax amount|total tax|vat amount",
    "total_amount": r"tong cong(?: tien thanh toan)?|tong tien thanh toan|tong thanh toan|grand total|total(?: amount)?",
    "currency": r"don vi tien te|loai tien|currency",
}
GENERIC = {
    "tax_id": r"ma so thue|mst|tax (?:id|code)",
    "address": r"dia chi|address",
    "name": r"ten don vi|company name",
}
LINE_LABELS = {
    "description": r"ten hang(?: hoa)?(?:,? dich vu)?|hang hoa(?:,? dich vu)?|description|item",
    "unit": r"don vi tinh|dvt|unit",
    "quantity": r"so luong|sl|quantity|qty",
    "unit_price": r"don gia|unit price|price",
    "amount": r"thanh tien|amount",
}
TAX_LABELS = {
    "rate": r"thue suat(?: gtgt)?|tax rate|vat",
    "taxable_amount": r"tien tinh thue|gia tri tinh thue|taxable amount",
    "tax_amount": r"tien thue(?: gtgt)?|tax amount",
}
CURRENCY_PATTERN = re.compile(
    r"(?<!\w)(?:VND|VNĐ|USD|EUR|GBP|JPY|CNY|đ)(?!\w)|[₫$€¥]", re.IGNORECASE
)


def label_match(value, patterns):
    normalized = text(value)
    matches = []
    for field, pattern in patterns.items():
        match = re.match(
            rf"^(?:{pattern})(?=\s|[:#：]|$)\s*[:#：]?\s*", folded(normalized)
        )
        if match:
            matches.append((match.end(), field))
    if not matches:
        return None
    end, field = max(matches)
    return field, normalized[end:]


def header_candidates(blocks, excluded):
    result = {field: [] for field in HEADER_FIELDS}
    anchors = []
    for block in blocks:
        match = label_match(block.text, LABELS)
        if (
            block.block_id not in excluded
            and match
            and match[0] in {"seller_name", "buyer_name"}
        ):
            anchors.append((match[0].split("_")[0], block))
    for block in blocks:
        if block.block_id in excluded:
            continue
        match = label_match(block.text, LABELS)
        generic = label_match(block.text, GENERIC) if match is None else None
        explicit = True
        context = []
        if generic:
            suffix, value = generic
            # Relative section geometry handles side-by-side roles even when
            # reading order interleaves seller and buyer blocks.
            nearby = [
                (
                    abs(block.left - anchor.left) + abs(block.top - anchor.top),
                    role,
                    anchor,
                )
                for role, anchor in anchors
                if anchor.page == block.page
                and anchor.top <= block.top
                and anchor.block_id != block.block_id
            ]
            nearby.sort(key=lambda item: (item[0], item[2].reading_order))
            unclear = (
                len(nearby) > 1
                and nearby[0][1] != nearby[1][1]
                and abs(nearby[0][0] - nearby[1][0]) < block.height
            )
            if nearby and not unclear:
                _, role, role_block = nearby[0]
                field = f"{role}_{suffix}"
                context = [role_block]
                match = (field, value)
            elif suffix == "tax_id":
                # Preserve unassigned tax evidence for both roles, never guess seller.
                for field in ("seller_tax_id", "buyer_tax_id"):
                    result[field].append(
                        Candidate(value, (block,), explicit_role=False)
                    )
        if match:
            field, value = match
            if field not in result:
                continue
            sources = context + [block]
            if not value:
                neighbors = [
                    b
                    for b in blocks
                    if b.block_id not in excluded
                    and b.block_id != block.block_id
                    and same_row(b, block)
                    and b.left >= block.right
                    and not label_match(b.text, LABELS)
                    and not label_match(b.text, GENERIC)
                ]
                if neighbors:
                    nearest = min(neighbors, key=lambda b: (b.left, b.reading_order))
                    value = nearest.text
                    sources.append(nearest)
            # The generic date label retains its word form for explicit component dates.
            if field == "invoice_date" and "thang" in folded(value):
                value = "ngày " + value
            result[field].append(
                Candidate(value, tuple(dict.fromkeys(sources)), explicit)
            )
        for marker in CURRENCY_PATTERN.finditer(block.text):
            result["currency"].append(Candidate(marker.group(), (block,)))
    return result


def visual_rows(blocks):
    rows = []
    for block in sorted(blocks, key=lambda b: (b.page, b.top, b.left, b.reading_order)):
        matches = [row for row in rows if same_row(row[0], block, ROW_OVERLAP)]
        if matches:
            min(matches, key=lambda row: abs(row[0].top - block.top)).append(block)
        else:
            rows.append([block])
    return [sorted(row, key=lambda b: (b.left, b.reading_order)) for row in rows]


def table_header(row, patterns):
    columns = {}
    for block in row:
        match = label_match(block.text, patterns)
        if match and not match[1]:
            columns[match[0]] = block
    return columns


def table_regions(blocks):
    """Detect tables by semantic headers; carry columns only within a page."""
    regions = []
    current = None
    excluded = set()
    for row in visual_rows(blocks):
        line_columns = table_header(row, LINE_LABELS)
        tax_columns = table_header(row, TAX_LABELS)
        if "description" in line_columns and len(line_columns) >= 2:
            current = ("line", line_columns, [])
            regions.append(current)
            excluded.update(b.block_id for b in row)
            continue
        if "rate" in tax_columns and len(tax_columns) >= 2:
            current = ("tax", tax_columns, [])
            regions.append(current)
            excluded.update(b.block_id for b in row)
            continue
        if current:
            _, columns, data = current
            if (
                row[0].page != next(iter(columns.values())).page
                or any(label_match(b.text, LABELS) for b in row)
                or any(
                    re.match(
                        r"^(?:nguoi |ky ten|signature|ghi chu|notes?\b|chi dung de\b|cam on\b|thank you\b)",
                        folded(b.text),
                    )
                    for b in row
                )
            ):
                current = None
            else:
                data.append(row)
                excluded.update(b.block_id for b in row)
    return regions, excluded


def group_columns(row, columns):
    groups = {field: [] for field in columns}
    centers = {field: (b.left + b.right) / 2 for field, b in columns.items()}
    for block in row:
        # Left alignment handles long descriptions; center alignment handles numbers.
        field = min(
            columns,
            key=lambda f: min(
                abs(block.left - columns[f].left),
                abs((block.left + block.right) / 2 - centers[f]),
            ),
        )
        groups[field].append(block)
    return groups


def row_metadata(row):
    cells = [row[f] for f in LINE_FIELDS]
    row["source_block_ids"] = list(
        dict.fromkeys(i for c in cells for i in c["source_block_ids"])
    )
    row["review_policy_version"] = REVIEW_VERSION
    row["review_reasons"] = list(
        dict.fromkeys(r for c in cells for r in c["review_reasons"])
    )
    row["machine_needs_review"] = any(c["machine_needs_review"] for c in cells)


def extract_tables(regions, currency):
    lines, taxes = [], []
    for kind, columns, rows in regions:
        grouped = []
        continuations = set()
        previous_bottom = None
        for row in rows:
            groups = group_columns(row, columns)
            nonempty = {f for f, values in groups.items() if values}
            if (
                kind == "line"
                and nonempty == {"description"}
                and grouped
                and min(b.top for b in row) - previous_bottom
                <= CONTINUATION_HEIGHTS * max(b.height for b in row)
            ):
                grouped[-1]["description"].extend(groups["description"])
                # A description-only fragment could also be a partial new item.
                # Preserve its evidence and surface the grouping uncertainty.
                continuations.add(len(grouped) - 1)
            else:
                grouped.append(groups)
            previous_bottom = max(b.bottom for b in row)
        for group_index, groups in enumerate(grouped):
            fields = LINE_FIELDS if kind == "line" else tuple(TAX_LABELS)
            item = {}
            for field in fields:
                sources = sorted(
                    groups.get(field, []), key=lambda b: (b.page, b.reading_order)
                )
                candidates = (
                    [Candidate("\n".join(b.text for b in sources), tuple(sources))]
                    if sources
                    else []
                )
                item[field] = select(
                    field,
                    candidates,
                    currency=currency,
                    absent=field == "unit" and field not in columns,
                )
                # Multiple numeric blocks in one cell are preserved for review.
                if len(sources) > 1 and field not in {"description", "unit"}:
                    item[field].update(
                        value_status="AMBIGUOUS",
                        normalized_value=None,
                        normalization=None,
                    )
                    add_reason(item[field], "MULTIPLE_CANDIDATES")
            if kind == "line":
                if group_index in continuations:
                    add_reason(item["description"], "AMBIGUOUS_FORMAT")
                item["line_id"] = f"line-{len(lines) + 1:04d}"
                row_metadata(item)
                lines.append(item)
            else:
                taxes.append(item)
    return lines, taxes


def inline_taxes(blocks, excluded, currency):
    """Explicit printed rate + labeled amounts, including nonstandard categories."""
    taxes = []
    pattern = re.compile(
        r"^(?:vat|thue suat(?: gtgt)?)\s*:?\s*([0-9]+(?:[.,][0-9]+)?\s*%|kct|kkkt)",
        re.IGNORECASE,
    )
    for row in visual_rows([b for b in blocks if b.block_id not in excluded]):
        for block in row:
            match = pattern.match(folded(block.text))
            if not match:
                continue
            item = {
                "rate": select(
                    "rate", [Candidate(match.group(1), (block,))], currency=currency
                )
            }
            for field in ("taxable_amount", "tax_amount"):
                candidates = []
                for source in row:
                    # Supports a single block with semicolon-separated labels too.
                    for segment in source.text.split(";"):
                        found = label_match(segment.strip(), {field: TAX_LABELS[field]})
                        if found:
                            candidates.append(Candidate(found[1], (source,)))
                item[field] = select(field, candidates, currency=currency)
            taxes.append(item)
    return taxes
