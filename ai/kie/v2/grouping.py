"""Opt-in geometry experiment; no OCR repair or numeric value inference."""

import re

from .extraction import LINE_LABELS, group_columns

# Exact observed header alias from TV2 train VRSYN2-00001; no fuzzy OCR repair.
EXPERIMENT_LINE_LABELS = {
    **LINE_LABELS,
    "description": r"ten hang(?: hoa)?\s*/\s*dich vu|" + LINE_LABELS["description"],
}
EXPERIMENT_LINE_STOP = r"^thue suat(?: gtgt)?\s*[:：]"


def interval_columns(row, columns):
    """Prefer unique header containment for short numeric cells.

    Narrow right-aligned numbers can be nearer the next header's left edge than
    their own header's center. Only a block fully contained in exactly one header
    span, belonging to a numeric column, overrides the baseline. Overlap, gutters,
    merged cells and non-numeric text fall back without inventing boundaries.
    """
    groups = {field: [] for field in columns}
    for block in row:
        contained = [
            field
            for field, header in columns.items()
            if header.left <= block.left and block.right <= header.right
        ]
        if (
            len(contained) == 1
            and contained[0] in {"quantity", "unit_price", "amount"}
            and re.fullmatch(r"[0-9]+(?:[.,][0-9]+)*", block.text.strip())
        ):
            groups[contained[0]].append(block)
        else:
            for field, blocks in group_columns([block], columns).items():
                groups[field].extend(blocks)
    return groups
