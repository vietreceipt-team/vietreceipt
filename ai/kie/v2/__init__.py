"""Public TV4 provider: V2_KIE_CALLABLE=ai.kie.v2:extract_invoice."""

from uuid import UUID

from .cells import add_reason, select
from .config import (
    BASELINE_GROUPING,
    GROUPING_EXTRACTORS,
    GROUPING_CONFIGURATIONS,
    HEADER_FIELDS,
    INTERVAL_GROUPING,
    LAYOUT_CONFIGURATION,
    LAYOUT_EXTRACTOR,
    LAYOUT_SCORE_VERSION,
)
from .consistency import check
from .evidence import flatten
from .normalization import folded
from .extraction import extract_tables, header_candidates, inline_taxes, table_regions
from .header import extract_header_candidates


def extract_invoice(evidence: dict, *, kie_run_id: UUID) -> dict:
    return extract_with_grouping(
        evidence, kie_run_id=kie_run_id, grouping=BASELINE_GROUPING
    )


def extract_with_grouping(evidence: dict, *, kie_run_id: UUID, grouping: str) -> dict:
    """Explicit experimental entry point; the worker provider stays baseline."""
    return _extract(evidence, kie_run_id=kie_run_id, grouping=grouping)


def extract_with_layout(evidence: dict, *, kie_run_id: UUID) -> dict:
    """Internal opt-in header variant; the public provider stays baseline."""
    return _extract(
        evidence, kie_run_id=kie_run_id, grouping=BASELINE_GROUPING, header_layout=True
    )


def _extract(evidence, *, kie_run_id, grouping, header_layout=False):
    if grouping not in GROUPING_CONFIGURATIONS:
        raise ValueError(f"Unknown grouping: {grouping}")
    if not isinstance(kie_run_id, UUID):
        raise TypeError("kie_run_id must be uuid.UUID")
    blocks = flatten(evidence)
    if grouping == INTERVAL_GROUPING:
        from .grouping import EXPERIMENT_LINE_LABELS, EXPERIMENT_LINE_STOP

        regions, excluded = table_regions(
            blocks,
            line_labels=EXPERIMENT_LINE_LABELS,
            line_stop_pattern=EXPERIMENT_LINE_STOP,
            preserve_numeric_rows=True,
        )
    else:
        regions, excluded = table_regions(blocks)
    if header_layout:
        # Reuse the observed table-label alias as a region hint only. The
        # baseline table rows and exclusion set remain unchanged.
        from .grouping import EXPERIMENT_LINE_LABELS, EXPERIMENT_LINE_STOP

        hint_regions, _ = table_regions(
            blocks,
            line_labels=EXPERIMENT_LINE_LABELS,
            line_stop_pattern=EXPERIMENT_LINE_STOP,
            preserve_numeric_rows=True,
        )
        candidates = extract_header_candidates(
            blocks,
            excluded_block_ids=excluded,
            region_hints=hint_regions or regions,
        )
    else:
        candidates = header_candidates(blocks, excluded)
    currency_cell = select("currency", candidates["currency"])
    currency = currency_cell["normalized_value"]
    if currency is None and "UNSUPPORTED_CURRENCY" in currency_cell["review_reasons"]:
        currency = "UNSUPPORTED"
    fields = {
        field: select(
            field, candidates[field], currency=currency, layout_aware=header_layout
        )
        for field in HEADER_FIELDS
    }
    fields["currency"] = currency_cell
    if header_layout:
        for cell in fields.values():
            cell["score_version"] = LAYOUT_SCORE_VERSION
    number = fields["invoice_number"]
    if number["normalized_value"] and number["normalized_value"].endswith("-"):
        add_reason(number, "AMBIGUOUS_FORMAT")
    if fields["seller_name"]["value_status"] == "PRESENT" and any(
        c.value == fields["seller_name"]["predicted_value"]
        and c.blocks[0].text in c.value
        for c in candidates["seller_name"]
    ):
        add_reason(fields["seller_name"], "SOURCE_ROLE_UNCLEAR")
    if (
        currency == "VND"
        and currency_cell["raw_text"]
        and "hoadon" in folded(currency_cell["raw_text"]).replace(" ", "")
    ):
        add_reason(currency_cell, "AMBIGUOUS_FORMAT")
    line_grouper = None
    if grouping == INTERVAL_GROUPING:
        from .grouping import interval_columns

        line_grouper = interval_columns
    lines, taxes = extract_tables(regions, currency, line_grouper=line_grouper)
    taxes.extend(inline_taxes(blocks, excluded, currency))
    result = {
        "schema_version": "2.0",
        "receipt_id": evidence["receipt_id"],
        "kie_run_id": str(kie_run_id),
        "source_ocr_run_id": evidence["ocr_run_id"],
        "extractor": dict(
            LAYOUT_EXTRACTOR if header_layout else GROUPING_EXTRACTORS[grouping]
        ),
        "configuration": dict(
            LAYOUT_CONFIGURATION if header_layout else GROUPING_CONFIGURATIONS[grouping]
        ),
        "fields": fields,
        "line_items": lines,
        "tax_breakdown": taxes,
    }
    check(result)
    from .contract import validate_result

    validate_result(result, evidence, kie_run_id=kie_run_id)
    return result
