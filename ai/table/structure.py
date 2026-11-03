"""Opt-in table structure strategies over immutable, original-page Reader evidence.

The public region entry point is deliberately independent of the pending Layout
adapter. ``structure_rows`` is the proposed callback for that adapter after review.
No image, OCR, header/footer, normalization or worker policy is changed here.
"""

import math
from statistics import median

from ai.kie.v2.cells import Candidate, add_reason, select
from ai.kie.v2.config import BASELINE_GROUPING, GROUPING_CONFIGURATIONS, LINE_FIELDS
from ai.kie.v2.evidence import flatten
from ai.kie.v2.extraction import (
    extract_tables,
    row_metadata,
    table_regions,
    visual_rows,
)
from ai.kie.v2.grouping import EXPERIMENT_LINE_LABELS, EXPERIMENT_LINE_STOP

STRUCTURE_STRATEGY = "conservative_intervals_v1"
STRATEGIES = {
    BASELINE_GROUPING: dict(GROUPING_CONFIGURATIONS[BASELINE_GROUPING]),
    STRUCTURE_STRATEGY: {"name": "conservative-intervals", "version": "1.0.0"},
}


def _regions(blocks, strategy):
    options = {}
    if strategy == STRUCTURE_STRATEGY:
        options = {
            "line_labels": EXPERIMENT_LINE_LABELS,
            "line_stop_pattern": EXPERIMENT_LINE_STOP,
            "preserve_numeric_rows": True,
        }
    regions, _ = table_regions(blocks, **options)
    return [region for region in regions if region[0] == "line"]


def _groups(row, columns):
    """Use header gaps as intervals; retain cross-column blocks in every owner.

    Text spanning two columns cannot safely be split into invented OCR tokens.
    Both affected cells carry the original block and an ambiguity status instead.
    """
    ordered = sorted(columns, key=lambda field: columns[field].left)
    boundaries = [0.0]
    for left, right in zip(ordered, ordered[1:]):
        a, b = columns[left], columns[right]
        boundary = (a.right + b.left) / 2
        if a.right > b.left:
            boundary = (a.left + a.right + b.left + b.right) / 4
        boundaries.append(boundary)
    boundaries.append(1.0)
    groups = {field: [] for field in columns}
    uncertain = set()
    for block in row:
        overlaps = [
            max(0, min(block.right, end) - max(block.left, start))
            for start, end in zip(boundaries, boundaries[1:])
        ]
        owners = [
            field
            for field, overlap in zip(ordered, overlaps)
            if overlap / (block.right - block.left) > 0.2
        ]
        if len(owners) > 1:
            uncertain.update(owners)
        if not owners:
            owners = [ordered[max(range(len(ordered)), key=overlaps.__getitem__)]]
        for field in owners:
            groups[field].append(block)
    return groups, uncertain


def _bounds(groups):
    blocks = {b.block_id: b for values in groups.values() for b in values}.values()
    blocks = list(blocks)
    return min(b.top for b in blocks), max(b.bottom for b in blocks)


def _logical_rows(rows, columns):
    blocks = list({b.block_id: b for row in rows for b in row}.values())
    if not blocks:
        return []
    typical_height = median(b.height for b in blocks)
    tall = [b for b in blocks if b.height > 1.8 * typical_height]
    if tall:
        # A tall first-column box must not become the visual-row anchor for
        # every numeric row it spans. Recluster normal-height evidence first.
        rows = visual_rows([b for b in blocks if b not in tall])
        for block in tall:
            owners = [
                row
                for row in rows
                if block.top
                < median((b.top + b.bottom) / 2 for b in row)
                < block.bottom
            ]
            if owners:
                for row in owners:
                    row.append(block)
            else:
                rows.append([block])
    logical = []
    for physical in rows:
        groups, uncertain = _groups(physical, columns)
        occupied = {field for field, values in groups.items() if values}
        top, bottom = _bounds(groups)
        height = max(b.height for b in physical)
        continuation = False
        join = False
        if logical:
            previous, previous_uncertain = logical[-1]
            previous_fields = {f for f, values in previous.items() if values}
            previous_top, previous_bottom = _bounds(previous)
            # A staggered fragment may complete a row only if columns do not
            # conflict and vertical centers remain within 1.5 source text heights.
            join = (
                not occupied & previous_fields
                and abs((top + bottom - previous_top - previous_bottom) / 2)
                <= 1.5 * height
            )
            continuation = (
                occupied == {"description"}
                and "description" in previous_fields
                and top - previous_bottom <= 1.8 * height
            )
            if join or continuation:
                for field, values in groups.items():
                    previous.setdefault(field, []).extend(values)
                previous_uncertain.update(uncertain)
                # Even a plausible continuation can be another partial item.
                previous_uncertain.add("description")
        if not (join or continuation):
            logical.append((groups, set(uncertain)))

    # Vertically merged source blocks can touch multiple physical rows. Keep
    # each original ID in the affected rows and require review; never duplicate
    # a number as a confident value in two items.
    snapshots = [
        {field: tuple(values) for field, values in groups.items()}
        for groups, _ in logical
    ]
    centers = []
    for groups in snapshots:
        unique = {b.block_id: b for values in groups.values() for b in values}.values()
        unique = list(unique)
        short_height = min(b.height for b in unique)
        centers.append(
            median(
                (b.top + b.bottom) / 2 for b in unique if b.height <= 1.5 * short_height
            )
        )
    for i, original in enumerate(snapshots):
        _, uncertain = logical[i]
        for j, (other, other_uncertain) in enumerate(logical):
            if i == j:
                continue
            for field, values in original.items():
                for block in values:
                    if block.top < centers[j] < block.bottom:
                        if block not in other.setdefault(field, []):
                            other[field].append(block)
                        uncertain.add(field)
                        other_uncertain.add(field)
    return logical


def structure_rows(blocks, *, currency=None, strategy=STRUCTURE_STRATEGY):
    """Return V2 rows from validated, region-selected ``Block`` objects.

    Regions must include recognizable column headers. Each page starts a new
    table; no cross-page continuation is guessed without a repeated header.
    ``currency`` comes from the caller's metadata, never arithmetic inference.
    """
    if strategy not in STRATEGIES:
        raise ValueError(f"Unknown table structure strategy: {strategy}")
    if currency is not None and not isinstance(currency, str):
        raise ValueError("currency must be a canonical currency string or None")
    regions = _regions(blocks, strategy)
    if strategy == BASELINE_GROUPING:
        return extract_tables(regions, currency)[0]
    lines = []
    for _, columns, physical_rows in regions:
        logical = _logical_rows(physical_rows, columns)
        for groups, uncertain in logical:
            item = {}
            for field in LINE_FIELDS:
                sources = sorted(
                    {b.block_id: b for b in groups.get(field, [])}.values(),
                    key=lambda b: (b.page, b.reading_order),
                )
                candidates = (
                    [Candidate("\n".join(b.text for b in sources), tuple(sources))]
                    if sources
                    else []
                )
                cell = select(
                    field,
                    candidates,
                    currency=currency,
                    absent=field == "unit" and field not in columns,
                )
                if field in uncertain or (
                    len(sources) > 1 and field not in {"description", "unit"}
                ):
                    add_reason(cell, "AMBIGUOUS_FORMAT")
                    # Joined descriptions can retain their selected text for
                    # review. Merged/split numeric and unit cells stay unknown.
                    if (
                        field != "description"
                        or any(
                            b in groups.get(other, [])
                            for b in sources
                            for other in LINE_FIELDS
                            if other != field
                        )
                        or any(
                            b in other_groups.get(field, [])
                            for b in sources
                            for other_groups, _ in logical
                            if other_groups is not groups
                        )
                    ):
                        cell.update(
                            value_status="AMBIGUOUS",
                            normalized_value=None,
                            normalization=None,
                        )
                item[field] = cell
            item["line_id"] = f"line-{len(lines) + 1:04d}"
            row_metadata(item)
            lines.append(item)
    return lines


def extract_table_structure(
    evidence, *, page_index, bbox, currency=None, strategy=STRUCTURE_STRATEGY
):
    """Reviewable region API, matching PR #76's original-page boundary rules.

    This does not register a strategy in the invoice provider or Layout adapter.
    A crossing block is an explicit region error, never a silently clipped cell.
    """
    if strategy not in STRATEGIES:
        raise ValueError(f"Unknown table structure strategy: {strategy}")
    blocks = flatten(evidence)
    pages = (
        len(evidence["pages"]) if evidence["schema_version"] == "document-2.0" else 1
    )
    if type(page_index) is not int or not 0 <= page_index < pages:
        raise ValueError("page_index is outside the evidence document")
    if (
        not isinstance(bbox, (tuple, list))
        or len(bbox) != 4
        or any(type(v) not in (int, float) or not math.isfinite(v) for v in bbox)
        or not (0 <= bbox[0] < bbox[2] <= 1 and 0 <= bbox[1] < bbox[3] <= 1)
    ):
        raise ValueError("bbox must have positive area within [0, 1]")
    left, top, right, bottom = bbox
    selected = []
    for block in blocks:
        if block.page != page_index:
            continue
        contained = (
            left <= block.left
            and block.right <= right
            and top <= block.top
            and block.bottom <= bottom
        )
        intersects = (
            block.left < right
            and left < block.right
            and block.top < bottom
            and top < block.bottom
        )
        if intersects and not contained:
            raise ValueError(f"Region boundary crosses source block: {block.block_id}")
        if contained:
            selected.append(block)
    rows = structure_rows(selected, currency=currency, strategy=strategy)
    regions = _regions(selected, strategy)
    covered = {
        b.block_id
        for _, columns, data in regions
        for b in [*columns.values(), *(b for row in data for b in row)]
    }
    unassigned = [b.block_id for b in selected if b.block_id not in covered]
    return {
        "strategy": dict(STRATEGIES[strategy]),
        "receipt_id": evidence["receipt_id"],
        "source_ocr_run_id": evidence["ocr_run_id"],
        "page_index": page_index,
        "bbox": list(bbox),
        "status": "EXTRACTED" if rows else "NO_ROWS_DETECTED",
        "machine_needs_review": bool(unassigned)
        or not rows
        or any(row["machine_needs_review"] for row in rows),
        "unassigned_block_ids": unassigned,
        "source_block_ids": [b.block_id for b in selected],
        "line_items": rows,
    }
