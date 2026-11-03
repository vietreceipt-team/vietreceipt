"""Reuse versioned KIE grouping on Layout regions in original page coordinates."""

import math

from ai.kie.v2.config import (
    BASELINE_GROUPING,
    GROUPING_CONFIGURATIONS,
    GROUPING_EXTRACTORS,
    INTERVAL_GROUPING,
)
from ai.kie.v2.evidence import flatten
from ai.kie.v2.extraction import extract_tables, table_regions


def extract_table(
    evidence: dict,
    *,
    page_index: int,
    bbox: tuple[float, float, float, float],
    currency: str | None = None,
    grouping: str = BASELINE_GROUPING,
) -> dict:
    """Return V2 line-item cells for one explicit Layout region.

    bbox is normalized (left, top, right, bottom) on the original page, NOT
    crop-local pixels. Blocks crossing the region boundary raise ValueError:
    silently truncating an OCR block could lose cells or alter source evidence.
    The caller owns currency provenance and whole-invoice consistency checks.
    """
    if type(page_index) is not int or page_index < 0:
        raise ValueError("page_index must be a nonnegative integer")
    if (
        not isinstance(bbox, (tuple, list))
        or len(bbox) != 4
        or any(type(v) not in (int, float) or not math.isfinite(v) for v in bbox)
    ):
        raise ValueError("bbox must contain four finite normalized coordinates")
    left, top, right, bottom = bbox
    if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
        raise ValueError("bbox must have positive area within [0, 1]")
    if grouping not in GROUPING_CONFIGURATIONS:
        raise ValueError(f"Unknown grouping: {grouping}")
    if currency is not None and not isinstance(currency, str):
        raise ValueError("currency must be a canonical currency string or None")

    blocks = flatten(evidence)
    page_count = (
        len(evidence["pages"]) if evidence["schema_version"] == "document-2.0" else 1
    )
    if page_index >= page_count:
        raise ValueError("page_index is outside the evidence document")
    selected = []
    for block in blocks:
        if block.page != page_index:
            continue
        intersects = (
            block.left < right
            and left < block.right
            and block.top < bottom
            and top < block.bottom
        )
        contained = (
            left <= block.left
            and block.right <= right
            and top <= block.top
            and block.bottom <= bottom
        )
        if intersects and not contained:
            raise ValueError(f"Region boundary crosses source block: {block.block_id}")
        if contained:
            selected.append(block)

    options = {}
    grouper = None
    if grouping == INTERVAL_GROUPING:
        from ai.kie.v2.grouping import (
            EXPERIMENT_LINE_LABELS,
            EXPERIMENT_LINE_STOP,
            interval_columns,
        )

        options = {
            "line_labels": EXPERIMENT_LINE_LABELS,
            "line_stop_pattern": EXPERIMENT_LINE_STOP,
            "preserve_numeric_rows": True,
        }
        grouper = interval_columns
    regions, _ = table_regions(selected, **options)
    line_regions = [region for region in regions if region[0] == "line"]
    rows, _ = extract_tables(line_regions, currency, line_grouper=grouper)
    return {
        "adapter_version": "table-region-0.1.0",
        "receipt_id": evidence["receipt_id"],
        "source_ocr_run_id": evidence["ocr_run_id"],
        "page_index": page_index,
        "bbox": list(bbox),
        "extractor": dict(GROUPING_EXTRACTORS[grouping]),
        "configuration": dict(GROUPING_CONFIGURATIONS[grouping]),
        "status": "EXTRACTED" if rows else "NO_ROWS_DETECTED",
        "source_block_ids": [block.block_id for block in selected],
        "line_items": rows,
    }
