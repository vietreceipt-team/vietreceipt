"""Compose explicit Layout regions into the existing validated invoice pipeline."""

from uuid import UUID

from ai.kie.v2.config import BASELINE_GROUPING

from .extractor import _extract_region, _select_region


def extract_invoice_with_tables(
    evidence: dict, *, kie_run_id: UUID, regions: list[dict], grouping=BASELINE_GROUPING
) -> dict:
    """Extract an invoice using caller-supplied Layout table regions.

    regions contains {page_index, bbox} records on the original pages. An empty
    region list is an error, not permission to silently return no line items.
    This callable needs Layout output and does not detect regions itself.
    """
    from ai.kie.v2 import extract_with_grouping

    if not isinstance(regions, list) or not regions:
        raise ValueError("Layout must provide a nonempty list of table regions")
    return extract_with_grouping(
        evidence, kie_run_id=kie_run_id, grouping=grouping, layout_regions=regions
    )


def _prepare_tables(evidence, blocks, regions):
    if not isinstance(regions, list) or not regions:
        raise ValueError("Layout must provide a nonempty list of table regions")
    page_count = (
        len(evidence["pages"]) if evidence["schema_version"] == "document-2.0" else 1
    )
    prepared = []
    for region in regions:
        if not isinstance(region, dict) or set(region) != {"page_index", "bbox"}:
            raise ValueError("Each table region must contain page_index and bbox only")
        page, bbox = region["page_index"], region["bbox"]
        selected = _select_region(blocks, page_count, page, bbox)
        for other_page, other_bbox, _ in prepared:
            if page == other_page and (
                max(bbox[0], other_bbox[0]) < min(bbox[2], other_bbox[2])
                and max(bbox[1], other_bbox[1]) < min(bbox[3], other_bbox[3])
            ):
                raise ValueError("Table regions overlap on the same page")
        prepared.append((page, tuple(bbox), selected))
    return sorted(prepared, key=lambda r: (r[0], r[1][1], r[1][0]))


def _extract_prepared_tables(evidence, prepared, currency, grouping):
    rows = []
    for page, bbox, blocks in prepared:
        table = _extract_region(evidence, blocks, page, bbox, currency, grouping)
        if table["status"] != "EXTRACTED":
            raise ValueError(f"No table rows detected in region on page {page}: {bbox}")
        rows.extend(table["line_items"])
    for index, row in enumerate(rows, start=1):
        row["line_id"] = f"line-{index:04d}"
    return rows
