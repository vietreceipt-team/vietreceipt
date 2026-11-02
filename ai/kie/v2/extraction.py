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
from .header import LABELS, GENERIC, label_match, header_candidates

LINE_LABELS = {
    "description": r"ten hang(?: hoa)?(?:,? dich vu)?|mat hang|hang hoa(?:,? dich vu)?|description|item|revenue sharing of (?:the )?service",
    "unit": r"don vi tinh|dvt|unit",
    "quantity": r"so luong|sl|quantity|qty",
    "unit_price": r"don gia|gia|unit price|price",
    "amount": r"thanh tien|t\s*tien|amount",
}
TAX_LABELS = {
    "rate": r"thue suat(?: gtgt)?|tax rate|vat",
    "taxable_amount": r"tien tinh thue|gia tri tinh thue|taxable amount",
    "tax_amount": r"tien thue(?: gtgt)?|tax amount",
}


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


def table_regions(
    blocks, *, line_labels=None, line_stop_pattern=None, preserve_numeric_rows=False
):
    """Detect tables by semantic headers; carry columns only within a page."""
    regions = []
    current = None
    excluded = set()
    for row in visual_rows(blocks):
        line_columns = table_header(
            row, LINE_LABELS if line_labels is None else line_labels
        )
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
            numeric_item = False
            if preserve_numeric_rows and current[0] == "line":
                cells = group_columns(row, columns)
                numeric_item = (
                    bool(cells.get("description"))
                    and sum(
                        len(cells.get(f, [])) == 1
                        and bool(
                            re.fullmatch(
                                r"[0-9]+(?:[.,][0-9]+)*", cells[f][0].text.strip()
                            )
                        )
                        for f in ("quantity", "unit_price", "amount")
                    )
                    >= 2
                )
            if (
                not data
                and "description" in columns
                and folded(columns["description"].text).startswith("revenue sharing")
                and all(re.fullmatch(r"\([^)]*\)", text(b.text)) for b in row)
            ):
                excluded.update(b.block_id for b in row)
                continue
            if (
                row[0].page != next(iter(columns.values())).page
                or (
                    current[0] == "line"
                    and line_stop_pattern is not None
                    and any(re.match(line_stop_pattern, folded(b.text)) for b in row)
                )
                or (not numeric_item and any(label_match(b.text, LABELS) for b in row))
                or (
                    not numeric_item
                    and any(
                        re.match(
                            r"^(?:tong sl\b|nguoi |ky ten|signature|ghi chu|notes?\b|chi dung de\b|cam on\b|thank you\b)",
                            folded(b.text),
                        )
                        for b in row
                    )
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


def extract_tables(regions, currency, *, line_grouper=None):
    lines, taxes = [], []
    for kind, columns, rows in regions:
        grouped = []
        continuations = set()
        previous_bottom = None
        for row in rows:
            grouper = line_grouper if kind == "line" and line_grouper else group_columns
            groups = grouper(row, columns)
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
